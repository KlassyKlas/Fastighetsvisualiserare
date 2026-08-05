"""Detaljplaner: listning med filter och upsert från datakällor."""

import logging

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.datasources import Bbox, DetailPlanIngest
from app.models import DetailPlan
from app.schemas import DetailPlanCollection
from app.services.geo import WGS84_SRID, geojson_to_element
from app.services.infrastructure import GEOJSON_DECIMALER
from app.services.serializers import detail_plan_feature

logger = logging.getLogger(__name__)


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


async def upsert_detail_plans(
    session: AsyncSession, items: list[DetailPlanIngest]
) -> tuple[int, int]:
    """Skriv in detaljplaner från en datakälla. Returnerar (upserted, skipped).

    Samma mönster som projektupserten: konflikt på external_id, en
    savepoint per rad så att ett trasigt objekt inte fäller hela synken.
    """
    upserted = 0
    skipped = 0

    for item in items:
        values = item.model_dump(exclude={"geometry"})
        if item.geometry is not None:
            try:
                values["geometry"] = geojson_to_element(
                    item.geometry, allowed_types=("MultiPolygon",)
                )
            except ValueError:
                logger.warning("Hoppar över detaljplan %s: ogiltig geometri", item.external_id)
                skipped += 1
                continue
        else:
            values["geometry"] = None

        stmt = pg_insert(DetailPlan).values(**values)
        update_columns = {
            key: getattr(stmt.excluded, key) for key in values if key != "external_id"
        }
        update_columns["updated_at"] = func.now()
        update_columns["geometry"] = func.coalesce(stmt.excluded.geometry, DetailPlan.geometry)
        stmt = stmt.on_conflict_do_update(
            index_elements=[DetailPlan.external_id], set_=update_columns
        )
        try:
            async with session.begin_nested():
                await session.execute(stmt)
            upserted += 1
        except SQLAlchemyError:
            logger.warning(
                "Hoppar över detaljplan %s: databasfel vid upsert",
                item.external_id,
                exc_info=True,
            )
            skipped += 1

    return upserted, skipped
