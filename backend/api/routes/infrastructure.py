import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2.functions import ST_MakeEnvelope, ST_Within
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy.orm import Session

from database.connection import get_db
from models.infrastructure import InfrastructureProject
from schemas.infrastructure import (
    InfrastructureProjectCollection,
    InfrastructureProjectCreate,
    InfrastructureProjectFeature,
    InfrastructureProjectProperties,
)
from services.trafikverket import TrafikverketDataSource

logger = logging.getLogger(__name__)

router = APIRouter()


def model_to_feature(project: InfrastructureProject) -> dict:
    """Convert an InfrastructureProject SQLAlchemy model to a GeoJSON Feature dict."""
    geometry = None
    if project.geometry is not None:
        try:
            shape = to_shape(project.geometry)
            geometry = mapping(shape)
        except Exception:
            logger.warning("Failed to convert geometry for project %s", project.id)

    properties = {
        "id": project.id,
        "external_id": project.external_id,
        "source": project.source,
        "name": project.name,
        "description": project.description,
        "project_type": project.project_type,
        "status": project.status,
        "start_date": project.start_date.isoformat() if project.start_date else None,
        "end_date": project.end_date.isoformat() if project.end_date else None,
        "budget_sek": project.budget_sek,
        "impact_radius_m": project.impact_radius_m,
        "metadata_json": project.metadata_json or {},
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }

    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": properties,
    }


@router.get("/projects", response_model=InfrastructureProjectCollection)
async def list_infrastructure_projects(
    status: str | None = Query(None, description="Filter by status"),
    project_type: str | None = Query(None, description="Filter by project type"),
    bbox: str | None = Query(
        None, description="Bounding box: west,south,east,north"
    ),
    db: Session = Depends(get_db),
):
    """List infrastructure projects as a GeoJSON FeatureCollection."""
    query = db.query(InfrastructureProject)

    if status:
        query = query.filter(InfrastructureProject.status == status)
    if project_type:
        query = query.filter(InfrastructureProject.project_type == project_type)
    if bbox:
        try:
            west, south, east, north = [float(c) for c in bbox.split(",")]
            envelope = ST_MakeEnvelope(west, south, east, north, 4326)
            query = query.filter(ST_Within(InfrastructureProject.geometry, envelope))
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail="Invalid bbox format. Use: west,south,east,north",
            )

    projects = query.all()
    features = [model_to_feature(p) for p in projects]

    return {"type": "FeatureCollection", "features": features}


@router.get("/projects/{project_id}", response_model=InfrastructureProjectFeature)
async def get_infrastructure_project(
    project_id: int,
    db: Session = Depends(get_db),
):
    """Get a single infrastructure project as a GeoJSON Feature."""
    project = db.query(InfrastructureProject).filter(
        InfrastructureProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return model_to_feature(project)


@router.post("/projects", response_model=InfrastructureProjectFeature, status_code=201)
async def create_infrastructure_project(
    data: InfrastructureProjectCreate,
    db: Session = Depends(get_db),
):
    """Create a new infrastructure project."""
    project = InfrastructureProject(
        external_id=data.external_id,
        source=data.source,
        name=data.name,
        description=data.description,
        project_type=data.project_type,
        status=data.status,
        start_date=data.start_date,
        end_date=data.end_date,
        budget_sek=data.budget_sek,
        impact_radius_m=data.impact_radius_m,
        metadata_json=data.metadata_json,
    )

    # Convert GeoJSON geometry to WKT for PostGIS
    if data.geometry:
        from shapely.geometry import shape as shapely_shape

        geom = shapely_shape(data.geometry)
        project.geometry = geom.wkt

    db.add(project)
    db.commit()
    db.refresh(project)

    return model_to_feature(project)


@router.post("/sync/trafikverket")
async def sync_trafikverket(db: Session = Depends(get_db)):
    """Fetch projects from Trafikverket API and upsert into database."""
    datasource = TrafikverketDataSource()
    projects_data = await datasource.fetch_infrastructure_projects()

    upserted = 0
    for proj_data in projects_data:
        external_id = proj_data.get("external_id")
        if not external_id:
            continue

        existing = db.query(InfrastructureProject).filter(
            InfrastructureProject.external_id == external_id
        ).first()

        geometry_wkt = None
        if proj_data.get("geometry"):
            from shapely.geometry import shape as shapely_shape

            try:
                geom = shapely_shape(proj_data["geometry"])
                geometry_wkt = geom.wkt
            except Exception:
                logger.warning(
                    "Failed to parse geometry for project %s", external_id
                )

        if existing:
            existing.name = proj_data.get("name", existing.name)
            existing.description = proj_data.get("description", existing.description)
            existing.project_type = proj_data.get("project_type", existing.project_type)
            existing.status = proj_data.get("status", existing.status)
            existing.start_date = proj_data.get("start_date", existing.start_date)
            existing.end_date = proj_data.get("end_date", existing.end_date)
            existing.metadata_json = proj_data.get(
                "metadata_json", existing.metadata_json
            )
            if geometry_wkt:
                existing.geometry = geometry_wkt
        else:
            project = InfrastructureProject(
                external_id=external_id,
                source="trafikverket",
                name=proj_data.get("name", "Okänt projekt"),
                description=proj_data.get("description"),
                project_type=proj_data.get("project_type", "övrigt"),
                status=proj_data.get("status", "pågående"),
                start_date=proj_data.get("start_date"),
                end_date=proj_data.get("end_date"),
                metadata_json=proj_data.get("metadata_json", {}),
            )
            if geometry_wkt:
                project.geometry = geometry_wkt
            db.add(project)

        upserted += 1

    db.commit()
    logger.info("Synced %d projects from Trafikverket", upserted)

    return {
        "status": "ok",
        "source": "trafikverket",
        "upserted_count": upserted,
        "total_fetched": len(projects_data),
    }
