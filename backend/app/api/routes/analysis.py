from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.domain import ProjectStatus, ProjectType
from app.schemas import AffectedPropertiesCollection
from app.services import analysis as analysis_service

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
