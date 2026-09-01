from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import BboxDep, SessionDep
from app.schemas import DetailPlanCollection, DetailPlanFeature
from app.services import planning as planning_service

router = APIRouter()


@router.get("/detail-plans", response_model=DetailPlanCollection)
async def list_detail_plans(
    session: SessionDep,
    bbox: BboxDep,
    status: Annotated[
        list[str] | None,
        Query(description="Filtrera på planstatus, t.ex. 'gällande' (kan upprepas)"),
    ] = None,
    municipality: Annotated[
        list[str] | None, Query(description="Filtrera på kommun (kan upprepas)")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DetailPlanCollection:
    """Detaljplaner som GeoJSON FeatureCollection, med filter och paginering.

    Detaljplaner är många — använd bbox (kartvyn) för att begränsa svaret.
    """
    return await planning_service.list_detail_plans(
        session,
        statuses=status,
        municipalities=municipality,
        bbox=bbox,
        limit=limit,
        offset=offset,
    )


@router.get("/detail-plans/{plan_id}", response_model=DetailPlanFeature)
async def get_detail_plan(session: SessionDep, plan_id: int) -> DetailPlanFeature:
    """En detaljplan med full geometri — t.ex. för att öppna en delad länk."""
    feature = await planning_service.get_detail_plan(session, plan_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Detaljplanen hittades inte")
    return feature
