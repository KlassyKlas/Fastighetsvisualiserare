from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import BboxDep, SessionDep, WriteAccess
from app.datasources import available_sources
from app.domain import ProjectStatus, ProjectType
from app.schemas import (
    ImpactZoneCollection,
    InfrastructureProjectCollection,
    InfrastructureProjectCreate,
    InfrastructureProjectFeature,
    SyncResult,
)
from app.services import infrastructure as infrastructure_service

router = APIRouter()


@router.get("/projects", response_model=InfrastructureProjectCollection)
async def list_projects(
    session: SessionDep,
    bbox: BboxDep,
    status: Annotated[
        list[ProjectStatus] | None, Query(description="Filtrera på status (kan upprepas)")
    ] = None,
    project_type: Annotated[
        list[ProjectType] | None,
        Query(description="Filtrera på projekttyp (kan upprepas)"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InfrastructureProjectCollection:
    """Infrastrukturprojekt som GeoJSON FeatureCollection, med filter och paginering."""
    return await infrastructure_service.list_projects(
        session,
        statuses=status,
        project_types=project_type,
        bbox=bbox,
        limit=limit,
        offset=offset,
    )


@router.get("/impact-zones", response_model=ImpactZoneCollection)
async def impact_zones(
    session: SessionDep,
    bbox: BboxDep,
    status: Annotated[list[ProjectStatus] | None, Query()] = None,
    project_type: Annotated[list[ProjectType] | None, Query()] = None,
) -> ImpactZoneCollection:
    """Påverkanszoner: projektgeometrier buffrade med sin påverkansradie i meter.

    Beräknas i PostGIS över geography, vilket ger korrekta zoner för
    punkter, linjer och ytor oavsett latitud.
    """
    return await infrastructure_service.impact_zones(
        session, statuses=status, project_types=project_type, bbox=bbox
    )


@router.get("/sources", response_model=dict[str, str])
async def list_sources() -> dict[str, str]:
    """Registrerade externa datakällor (namn → visningsnamn)."""
    return available_sources()


@router.get("/projects/{project_id}", response_model=InfrastructureProjectFeature)
async def get_project(session: SessionDep, project_id: int) -> InfrastructureProjectFeature:
    feature = await infrastructure_service.get_project(session, project_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Projektet hittades inte")
    return feature


@router.post(
    "/projects",
    response_model=InfrastructureProjectFeature,
    status_code=201,
    dependencies=[WriteAccess],
)
async def create_project(
    session: SessionDep, data: InfrastructureProjectCreate
) -> InfrastructureProjectFeature:
    return await infrastructure_service.create_project(session, data)


@router.post("/sync/{source_name}", response_model=SyncResult, dependencies=[WriteAccess])
async def sync_source(session: SessionDep, source_name: str, bbox: BboxDep) -> SyncResult:
    """Synkronisera en registrerad datakälla till databasen (upsert)."""
    return await infrastructure_service.sync_source(session, source_name, bbox)
