from fastapi import HTTPException
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.datasources import PropertyIngest
from app.domain import PropertyType
from app.models import Property
from app.schemas import PropertyCollection, PropertyCreate, PropertyFeature
from app.services.geo import WGS84_SRID, geojson_to_element
from app.services.serializers import property_feature


def _filter_conditions(
    *,
    municipalities: list[str] | None,
    property_types: list[PropertyType] | None,
    min_value: int | None,
    max_value: int | None,
    bbox: tuple[float, float, float, float] | None,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if municipalities:
        conditions.append(Property.municipality.in_(municipalities))
    if property_types:
        conditions.append(Property.property_type.in_(property_types))
    if min_value is not None:
        conditions.append(Property.assessed_value_sek >= min_value)
    if max_value is not None:
        conditions.append(Property.assessed_value_sek <= max_value)
    if bbox is not None:
        west, south, east, north = bbox
        # ST_Intersects (inte ST_Within): geometrier som korsar rutans
        # kant ska också med i svaret.
        conditions.append(
            func.ST_Intersects(
                Property.geometry,
                func.ST_MakeEnvelope(west, south, east, north, WGS84_SRID),
            )
        )
    return conditions


async def list_properties(
    session: AsyncSession,
    *,
    municipalities: list[str] | None = None,
    property_types: list[PropertyType] | None = None,
    min_value: int | None = None,
    max_value: int | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    limit: int = 500,
    offset: int = 0,
) -> PropertyCollection:
    conditions = _filter_conditions(
        municipalities=municipalities,
        property_types=property_types,
        min_value=min_value,
        max_value=max_value,
        bbox=bbox,
    )

    total = await session.scalar(select(func.count()).select_from(Property).where(*conditions))

    rows = await session.execute(
        select(Property, func.ST_AsGeoJSON(Property.geometry))
        .where(*conditions)
        .order_by(Property.id)
        .limit(limit)
        .offset(offset)
    )
    features = [property_feature(prop, geojson) for prop, geojson in rows.all()]

    return PropertyCollection(
        features=features,
        numberMatched=total or 0,
        numberReturned=len(features),
    )


async def search_properties(
    session: AsyncSession, query: str, limit: int = 50
) -> PropertyCollection:
    pattern = f"%{query}%"
    rows = await session.execute(
        select(Property, func.ST_AsGeoJSON(Property.geometry))
        .where(
            or_(
                Property.designation.ilike(pattern),
                Property.address.ilike(pattern),
                Property.owner_name.ilike(pattern),
                Property.city.ilike(pattern),
                Property.municipality.ilike(pattern),
            )
        )
        .order_by(Property.designation)
        .limit(limit)
    )
    features = [property_feature(prop, geojson) for prop, geojson in rows.all()]
    return PropertyCollection(
        features=features,
        numberMatched=len(features),
        numberReturned=len(features),
    )


async def get_property(session: AsyncSession, property_id: int) -> PropertyFeature | None:
    row = (
        await session.execute(
            select(Property, func.ST_AsGeoJSON(Property.geometry)).where(Property.id == property_id)
        )
    ).one_or_none()
    if row is None:
        return None
    prop, geojson = row
    return property_feature(prop, geojson)


async def create_property(session: AsyncSession, data: PropertyCreate) -> PropertyFeature:
    values = data.model_dump(exclude={"geometry"})
    prop = Property(**values)

    if data.geometry is not None:
        try:
            prop.geometry = geojson_to_element(data.geometry)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    session.add(prop)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"En fastighet med beteckningen '{data.designation}' finns redan",
        ) from exc
    await session.refresh(prop)

    geojson = await session.scalar(
        select(func.ST_AsGeoJSON(Property.geometry)).where(Property.id == prop.id)
    )
    return property_feature(prop, geojson)


async def upsert_properties(session: AsyncSession, items: list[PropertyIngest]) -> tuple[int, int]:
    """Skriv in fastigheter från en datakälla. Returnerar (upserted, skipped).

    Konflikthantering sker på fastighetsbeteckning (designation).
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    upserted = 0
    skipped = 0

    for item in items:
        values = item.model_dump(exclude={"geometry"})
        if item.geometry is not None:
            try:
                values["geometry"] = geojson_to_element(item.geometry)
            except ValueError:
                skipped += 1
                continue
        else:
            values["geometry"] = None

        stmt = pg_insert(Property).values(**values)
        update_columns = {
            key: getattr(stmt.excluded, key) for key in values if key != "designation"
        }
        update_columns["updated_at"] = func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=[Property.designation], set_=update_columns
        )
        await session.execute(stmt)
        upserted += 1

    return upserted, skipped
