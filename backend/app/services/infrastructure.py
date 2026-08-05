import logging
from datetime import date

from fastapi import HTTPException
from geoalchemy2 import Geography, Geometry
from sqlalchemy import ColumnElement, cast, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.datasources import (
    Bbox,
    DataSourceError,
    InfrastructureProjectIngest,
    UnknownDataSourceError,
    available_sources,
    get_datasource,
)
from app.domain import ProjectStatus, ProjectType
from app.models import InfrastructureProject
from app.schemas import (
    ImpactZoneCollection,
    InfrastructureProjectCollection,
    InfrastructureProjectCreate,
    InfrastructureProjectFeature,
    SyncResult,
)
from app.services import properties as property_service
from app.services.geo import WGS84_SRID, geojson_to_element
from app.services.serializers import impact_zone_feature, project_feature

logger = logging.getLogger(__name__)

# 6 decimaler ≈ 0,1 m — mer precision är brus som fördubblar payloaden
# (nationell plan-korridorerna är megabytestora i full precision).
GEOJSON_DECIMALER = 6
# Påverkanszoner är visuella hjälpytor: förenkla med ~20 m tolerans så
# att buffrade korridorer inte skickar tiotusentals hörn per svar.
ZON_FORENKLING_GRADER = 0.0002


def _filter_conditions(
    *,
    statuses: list[ProjectStatus] | None,
    project_types: list[ProjectType] | None,
    bbox: Bbox | None,
    year: int | None = None,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if statuses:
        conditions.append(InfrastructureProject.status.in_(statuses))
    if project_types:
        conditions.append(InfrastructureProject.project_type.in_(project_types))
    if year is not None:
        # Projektet är aktivt någon gång under året; okänt datum
        # utesluter inte (samma semantik som demo-filtret i frontenden)
        conditions.append(
            or_(
                InfrastructureProject.start_date.is_(None),
                InfrastructureProject.start_date <= date(year, 12, 31),
            )
        )
        conditions.append(
            or_(
                InfrastructureProject.end_date.is_(None),
                InfrastructureProject.end_date >= date(year, 1, 1),
            )
        )
    if bbox is not None:
        west, south, east, north = bbox
        conditions.append(
            func.ST_Intersects(
                InfrastructureProject.geometry,
                func.ST_MakeEnvelope(west, south, east, north, WGS84_SRID),
            )
        )
    return conditions


async def list_projects(
    session: AsyncSession,
    *,
    statuses: list[ProjectStatus] | None = None,
    project_types: list[ProjectType] | None = None,
    bbox: Bbox | None = None,
    year: int | None = None,
    limit: int = 500,
    offset: int = 0,
) -> InfrastructureProjectCollection:
    conditions = _filter_conditions(
        statuses=statuses, project_types=project_types, bbox=bbox, year=year
    )

    total = await session.scalar(
        select(func.count()).select_from(InfrastructureProject).where(*conditions)
    )

    rows = await session.execute(
        select(
            InfrastructureProject,
            func.ST_AsGeoJSON(InfrastructureProject.geometry, GEOJSON_DECIMALER),
        )
        .where(*conditions)
        .order_by(InfrastructureProject.id)
        .limit(limit)
        .offset(offset)
    )
    features = [project_feature(project, geojson) for project, geojson in rows.all()]

    return InfrastructureProjectCollection(
        features=features,
        numberMatched=total or 0,
        numberReturned=len(features),
    )


async def get_project(
    session: AsyncSession, project_id: int
) -> InfrastructureProjectFeature | None:
    row = (
        await session.execute(
            select(
                InfrastructureProject,
                func.ST_AsGeoJSON(InfrastructureProject.geometry, GEOJSON_DECIMALER),
            ).where(InfrastructureProject.id == project_id)
        )
    ).one_or_none()
    if row is None:
        return None
    project, geojson = row
    return project_feature(project, geojson)


async def create_project(
    session: AsyncSession, data: InfrastructureProjectCreate
) -> InfrastructureProjectFeature:
    values = data.model_dump(exclude={"geometry"})
    project = InfrastructureProject(**values)

    if data.geometry is not None:
        try:
            project.geometry = geojson_to_element(data.geometry)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    session.add(project)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Ett projekt med externt id '{data.external_id}' finns redan",
        ) from exc
    await session.refresh(project)

    geojson = await session.scalar(
        select(func.ST_AsGeoJSON(InfrastructureProject.geometry)).where(
            InfrastructureProject.id == project.id
        )
    )
    return project_feature(project, geojson)


async def impact_zones(
    session: AsyncSession,
    *,
    statuses: list[ProjectStatus] | None = None,
    project_types: list[ProjectType] | None = None,
    bbox: Bbox | None = None,
    year: int | None = None,
) -> ImpactZoneCollection:
    """Serverberäknade påverkanszoner: projektgeometrin buffrad med
    impact_radius_m i meter (via geography), för alla geometrityper —
    även linjer och ytor."""
    conditions = _filter_conditions(
        statuses=statuses, project_types=project_types, bbox=bbox, year=year
    )
    conditions.append(InfrastructureProject.geometry.is_not(None))

    # OBS: Geography(srid=4326) — utan srid renderas geography(GEOMETRY,-1)
    # som varken är giltig typmod eller matchar det funktionella indexet.
    # Bufferten förenklas innan serialisering (kräver geometry, därav
    # casten tillbaka) — en buffrad korridor har annars tiotusentals hörn.
    zone_geojson = func.ST_AsGeoJSON(
        func.ST_SimplifyPreserveTopology(
            cast(
                func.ST_Buffer(
                    cast(InfrastructureProject.geometry, Geography(srid=WGS84_SRID)),
                    InfrastructureProject.impact_radius_m,
                ),
                Geometry(srid=WGS84_SRID),
            ),
            ZON_FORENKLING_GRADER,
        ),
        GEOJSON_DECIMALER,
    )

    rows = await session.execute(
        select(
            InfrastructureProject.id,
            InfrastructureProject.name,
            InfrastructureProject.project_type,
            InfrastructureProject.status,
            InfrastructureProject.start_date,
            InfrastructureProject.end_date,
            InfrastructureProject.impact_radius_m,
            zone_geojson,
        )
        .where(*conditions)
        .order_by(InfrastructureProject.id)
    )

    features = [impact_zone_feature(*row) for row in rows.all()]
    return ImpactZoneCollection(features=features)


async def upsert_projects(
    session: AsyncSession, items: list[InfrastructureProjectIngest]
) -> tuple[int, int]:
    """Skriv in projekt från en datakälla. Returnerar (upserted, skipped).

    Konflikthantering sker på external_id i en enda upsert per rad —
    inga N+1-läsfrågor. Varje rad skrivs i en savepoint så att ett
    enskilt trasigt objekt räknas som skipped i stället för att fälla
    hela synkroniseringen.
    """
    upserted = 0
    skipped = 0

    for item in items:
        values = item.model_dump(exclude={"geometry"})
        if item.geometry is not None:
            try:
                values["geometry"] = geojson_to_element(item.geometry)
            except ValueError:
                logger.warning("Hoppar över projekt %s: ogiltig geometri", item.external_id)
                skipped += 1
                continue
        else:
            values["geometry"] = None

        stmt = pg_insert(InfrastructureProject).values(**values)
        update_columns = {
            key: getattr(stmt.excluded, key) for key in values if key != "external_id"
        }
        update_columns["updated_at"] = func.now()
        # Skriv aldrig över en befintlig geometri med NULL — Trafikverket
        # kan tillfälligt utelämna geometrin för ett objekt som tidigare
        # levererats med geometri.
        update_columns["geometry"] = func.coalesce(
            stmt.excluded.geometry, InfrastructureProject.geometry
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[InfrastructureProject.external_id], set_=update_columns
        )
        try:
            async with session.begin_nested():
                await session.execute(stmt)
            upserted += 1
        except SQLAlchemyError:
            logger.warning(
                "Hoppar över projekt %s: databasfel vid upsert",
                item.external_id,
                exc_info=True,
            )
            skipped += 1

    return upserted, skipped


async def sync_source(
    session: AsyncSession, source_name: str, bbox: Bbox | None = None
) -> SyncResult:
    """Hämta data från en registrerad källa och skriv in i databasen.

    Fel i källan rapporteras som HTTP-fel — aldrig som ett lyckat svar.
    """
    try:
        datasource = get_datasource(source_name)
    except UnknownDataSourceError as exc:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Okänd datakälla '{source_name}'. "
                f"Tillgängliga källor: {', '.join(available_sources()) or 'inga'}"
            ),
        ) from exc

    try:
        projects = await datasource.fetch_infrastructure_projects(bbox)
        properties = await datasource.fetch_properties(bbox)
    except DataSourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc

    projects_upserted, projects_skipped = await upsert_projects(session, projects)
    properties_upserted, properties_skipped = await property_service.upsert_properties(
        session, properties
    )
    await session.commit()

    return SyncResult(
        source=source_name,
        fetched=len(projects) + len(properties),
        upserted=projects_upserted + properties_upserted,
        skipped=projects_skipped + properties_skipped,
        truncated=datasource.truncated,
    )
