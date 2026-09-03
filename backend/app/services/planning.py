"""Detaljplaner: listning med filter och upsert från datakällor."""

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.datasources import Bbox, DetailPlanIngest
from app.models import DetailPlan
from app.schemas import DetailPlanCollection, DetailPlanFeature
from app.services.geo import WGS84_SRID
from app.services.infrastructure import GEOJSON_DECIMALER
from app.services.serializers import detail_plan_feature
from app.services.upsert import SyncCounts, upsert_rows


def _filter_conditions(
    *,
    statuses: list[str] | None,
    municipalities: list[str] | None,
    bbox: Bbox | None,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if statuses:
        conditions.append(DetailPlan.status.in_(statuses))
    if municipalities:
        conditions.append(DetailPlan.municipality.in_(municipalities))
    if bbox is not None:
        west, south, east, north = bbox
        conditions.append(
            func.ST_Intersects(
                DetailPlan.geometry,
                func.ST_MakeEnvelope(west, south, east, north, WGS84_SRID),
            )
        )
    return conditions


async def list_detail_plans(
    session: AsyncSession,
    *,
    statuses: list[str] | None = None,
    municipalities: list[str] | None = None,
    bbox: Bbox | None = None,
    limit: int = 500,
    offset: int = 0,
) -> DetailPlanCollection:
    conditions = _filter_conditions(statuses=statuses, municipalities=municipalities, bbox=bbox)

    total = await session.scalar(select(func.count()).select_from(DetailPlan).where(*conditions))

    rows = await session.execute(
        select(DetailPlan, func.ST_AsGeoJSON(DetailPlan.geometry, GEOJSON_DECIMALER))
        .where(*conditions)
        .order_by(DetailPlan.id)
        .limit(limit)
        .offset(offset)
    )
    features = [detail_plan_feature(plan, geojson) for plan, geojson in rows.all()]

    return DetailPlanCollection(
        features=features,
        numberMatched=total or 0,
        numberReturned=len(features),
    )


async def get_detail_plan(session: AsyncSession, plan_id: int) -> DetailPlanFeature | None:
    row = (
        await session.execute(
            select(DetailPlan, func.ST_AsGeoJSON(DetailPlan.geometry, GEOJSON_DECIMALER)).where(
                DetailPlan.id == plan_id
            )
        )
    ).one_or_none()
    if row is None:
        return None
    plan, geojson = row
    return detail_plan_feature(plan, geojson)


async def upsert_detail_plans(session: AsyncSession, items: list[DetailPlanIngest]) -> SyncCounts:
    """Skriv in detaljplaner från en datakälla (konflikt på external_id) — se services.upsert."""
    return await upsert_rows(
        session,
        DetailPlan,
        items,
        conflict_key="external_id",
        label="detaljplan",
        allowed_geometry_types=("MultiPolygon",),
    )
