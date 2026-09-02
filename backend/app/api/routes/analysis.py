from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.domain import ProjectStatus, ProjectType
from app.schemas import AffectedPropertiesCollection, ProximityScoresCollection
from app.services import analysis as analysis_service
from app.services.scoring import DEFAULT_MAX_DISTANCE_M

router = APIRouter()


@router.get("/affected-properties", response_model=AffectedPropertiesCollection)
async def affected_properties(
    session: SessionDep,
    status: Annotated[
        list[ProjectStatus] | None,
        Query(description="Begränsa till projekt med dessa statusar"),
    ] = None,
    project_type: Annotated[
        list[ProjectType] | None,
        Query(description="Begränsa till projekt av dessa typer"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> AffectedPropertiesCollection:
    """Fastigheter inom påverkansradien för matchande projekt.

    Varje fastighet får listan över påverkande projekt med avstånd i meter.
    """
    return await analysis_service.affected_properties(
        session, statuses=status, project_types=project_type, limit=limit
    )


@router.get("/proximity-scores", response_model=ProximityScoresCollection)
async def proximity_scores(
    session: SessionDep,
    status: Annotated[
        list[ProjectStatus] | None,
        Query(description="Räkna bara projekt med dessa statusar"),
    ] = None,
    project_type: Annotated[
        list[ProjectType] | None,
        Query(description="Räkna bara projekt av dessa typer"),
    ] = None,
    year: Annotated[
        int | None,
        Query(ge=1900, le=2100, description="Räkna bara projekt aktiva under detta år"),
    ] = None,
    owner: Annotated[
        str | None,
        Query(description="Ranka bara fastigheter med exakt denna ägare (owner_name)"),
    ] = None,
    max_distance_m: Annotated[
        float, Query(gt=0, le=50_000, description="Sökradie i meter")
    ] = DEFAULT_MAX_DISTANCE_M,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> ProximityScoresCollection:
    """Närhetspoäng: fastigheter rankade efter närhet till infrastruktur.

    Poängen är summan av viktade bidrag (typ, status, avstånd, budget,
    tid till färdigställande) från projekt inom sökradien — varje bidrag
    redovisas för sig så att rankningen alltid går att förklara.
    """
    return await analysis_service.proximity_scores(
        session,
        statuses=status,
        project_types=project_type,
        year=year,
        owner=owner,
        max_distance_m=max_distance_m,
        limit=limit,
    )
