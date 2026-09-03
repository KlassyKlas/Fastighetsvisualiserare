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
    SyncRunList,
)
from app.services import infrastructure as infrastructure_service

router = APIRouter()


YearQuery = Annotated[
    int | None,
    Query(ge=1900, le=2100, description="Visa bara projekt som är aktiva under detta år"),
]


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
    year: YearQuery = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InfrastructureProjectCollection:
    """Infrastrukturprojekt som GeoJSON FeatureCollection, med filter och paginering."""
    return await infrastructure_service.list_projects(
        session,
        statuses=status,
        project_types=project_type,
        bbox=bbox,
        year=year,
        limit=limit,
        offset=offset,
    )


@router.get("/impact-zones", response_model=ImpactZoneCollection)
async def impact_zones(
    session: SessionDep,
    bbox: BboxDep,
    status: Annotated[list[ProjectStatus] | None, Query()] = None,
    project_type: Annotated[list[ProjectType] | None, Query()] = None,
    year: YearQuery = None,
) -> ImpactZoneCollection:
    """Påverkanszoner: projektgeometrier buffrade med sin påverkansradie i meter.

    Zonerna är förberäknade i PostGIS (geography, vilket ger korrekta
    zoner för punkter, linjer och ytor oavsett latitud) och räknas om
    när projektet skrivs — anropet serialiserar bara. bbox filtrerar på
    zonen, inte på projektgeometrin: en zon som når in i kartvyn visas
    även om projektet ligger utanför.
    """
    return await infrastructure_service.impact_zones(
        session, statuses=status, project_types=project_type, bbox=bbox, year=year
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


@router.get("/sync/runs", response_model=SyncRunList)
async def list_sync_runs(
    session: SessionDep,
    source: Annotated[
        str | None, Query(min_length=1, description="Visa bara körningar för denna källa")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="Antal körningar, nyast först")] = 20,
) -> SyncRunList:
    """Synkloggen: senaste körningarna per anrop av POST /sync/{källa}.

    Lyckade som misslyckade (error satt). Senaste körningens started_at
    är tidsankaret "sedan senaste synk" i panelen Nytt sedan senast.
    """
    return await infrastructure_service.list_sync_runs(session, source=source, limit=limit)


@router.post("/sync/{source_name}", response_model=SyncResult, dependencies=[WriteAccess])
async def sync_source(session: SessionDep, source_name: str, bbox: BboxDep) -> SyncResult:
    """Synkronisera en registrerad datakälla till databasen (upsert)."""
    return await infrastructure_service.sync_source(session, source_name, bbox)
