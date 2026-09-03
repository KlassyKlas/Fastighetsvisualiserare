from typing import Any

from fastapi import HTTPException
from sqlalchemy import ColumnElement, Row, distinct, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.datasources import PropertyIngest
from app.domain import PropertyType
from app.models import Property
from app.schemas import (
    OwnerSummary,
    OwnerSummaryList,
    PropertyCollection,
    PropertyCreate,
    PropertyFeature,
)
from app.services.geo import WGS84_SRID, geojson_to_element
from app.services.serializers import property_feature
from app.services.upsert import SyncCounts, upsert_rows


def _filter_conditions(
    *,
    municipalities: list[str] | None,
    property_types: list[PropertyType] | None,
    min_value: int | None,
    max_value: int | None,
    bbox: tuple[float, float, float, float] | None,
    owner: str | None = None,
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
    if owner is not None:
        # Exakt match: ägarvyn utgår från ett namn ur ägarlistan, inte fritext.
        conditions.append(Property.owner_name == owner)
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
    owner: str | None = None,
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
        owner=owner,
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


def _owner_summary(row: Row[Any]) -> OwnerSummary:
    (
        owner_name,
        org_number,
        count,
        total_area,
        total_value,
        municipalities,
        west,
        south,
        east,
        north,
    ) = row
    return OwnerSummary(
        owner_name=owner_name,
        owner_org_number=org_number,
        property_count=count,
        total_area_sqm=float(total_area) if total_area is not None else None,
        # SUM över bigint ger numeric (Decimal via asyncpg) — tillbaka till int.
        total_assessed_value_sek=int(total_value) if total_value is not None else None,
        # Sorteras här, inte i SQL, så att ordningen inte beror på
        # databasens collation (demo-läget speglar samma enkla sortering).
        municipalities=sorted(municipalities or []),
        extent=None if west is None else [west, south, east, north],
    )


async def list_owners(
    session: AsyncSession,
    *,
    municipalities: list[str] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    limit: int = 50,
) -> OwnerSummaryList:
    """Ägare grupperade på exakt owner_name, med innehavets nyckeltal.

    Hela aggregeringen görs i PostGIS över samma filter som
    fastighetslistan: räkning, summor (SUM ignorerar NULL och ger NULL
    bara när alla saknar värde), distinkta kommuner och utbredningen via
    ST_Extent. Fastigheter utan ägare ingår inte.
    """
    conditions = _filter_conditions(
        municipalities=municipalities,
        property_types=None,
        min_value=None,
        max_value=None,
        bbox=bbox,
    )
    conditions.append(Property.owner_name.is_not(None))

    total = await session.scalar(
        select(func.count(distinct(Property.owner_name))).where(*conditions)
    )

    # ST_Extent är ett aggregat som ger en box2d; hörnen plockas ut som
    # fyra kolumner (ST_XMin m.fl. tar box2d). NULL när ingen fastighet
    # i gruppen har geometri — då saknar ägaren utbredning.
    extent = func.ST_Extent(Property.geometry)
    property_count = func.count().label("property_count")
    rows = await session.execute(
        select(
            Property.owner_name,
            func.min(Property.owner_org_number),
            property_count,
            func.sum(Property.area_sqm),
            func.sum(Property.assessed_value_sek),
            func.array_agg(distinct(Property.municipality)).filter(
                Property.municipality.is_not(None)
            ),
            func.ST_XMin(extent),
            func.ST_YMin(extent),
            func.ST_XMax(extent),
            func.ST_YMax(extent),
        )
        .where(*conditions)
        .group_by(Property.owner_name)
        .order_by(property_count.desc(), Property.owner_name)
        .limit(limit)
    )

    owners = [_owner_summary(row) for row in rows.all()]
    return OwnerSummaryList(owners=owners, numberMatched=total or 0, numberReturned=len(owners))


async def search_properties(
    session: AsyncSession, query: str, limit: int = 50
) -> PropertyCollection:
    pattern = f"%{query}%"
    search_condition = or_(
        Property.designation.ilike(pattern),
        Property.address.ilike(pattern),
        Property.owner_name.ilike(pattern),
        Property.city.ilike(pattern),
        Property.municipality.ilike(pattern),
    )

    total = await session.scalar(select(func.count()).select_from(Property).where(search_condition))
    rows = await session.execute(
        select(Property, func.ST_AsGeoJSON(Property.geometry))
        .where(search_condition)
        .order_by(Property.designation)
        .limit(limit)
    )
    features = [property_feature(prop, geojson) for prop, geojson in rows.all()]
    return PropertyCollection(
        features=features,
        numberMatched=total or 0,
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
            prop.geometry = geojson_to_element(data.geometry, allowed_types=("MultiPolygon",))
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


async def upsert_properties(session: AsyncSession, items: list[PropertyIngest]) -> SyncCounts:
    """Skriv in fastigheter från en datakälla (konflikt på fastighetsbeteckning)
    — se services.upsert."""
    return await upsert_rows(
        session,
        Property,
        items,
        conflict_key="designation",
        label="fastighet",
        allowed_geometry_types=("MultiPolygon",),
    )
