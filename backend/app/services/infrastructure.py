import logging
from datetime import date

from fastapi import HTTPException
from sqlalchemy import ColumnElement, func, insert, or_, select, update
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
from app.models import InfrastructureProject, SyncRun
from app.schemas import (
    ImpactZoneCollection,
    InfrastructureProjectCollection,
    InfrastructureProjectCreate,
    InfrastructureProjectFeature,
    SyncResult,
    SyncRunInfo,
    SyncRunList,
)
from app.services import properties as property_service
from app.services.geo import WGS84_SRID, geojson_to_element
from app.services.serializers import impact_zone_feature, project_feature
from app.services.upsert import changed_where

logger = logging.getLogger(__name__)

# 6 decimaler ≈ 0,1 m — mer precision är brus som fördubblar payloaden
# (nationell plan-korridorerna är megabytestora i full precision).
GEOJSON_DECIMALER = 6


def _filter_conditions(
    *,
    statuses: list[ProjectStatus] | None,
    project_types: list[ProjectType] | None,
    bbox: Bbox | None,
    year: int | None = None,
    bbox_column: ColumnElement | None = None,
) -> list[ColumnElement[bool]]:
    """Gemensamma filter för projektlistan och påverkanszonerna.

    bbox_column: vilken geometri bbox-filtret går mot — projektgeometrin
    (standard) eller den lagrade zonen (påverkanszonsfrågan: en zon kan
    nudda kartvyn fast projektet ligger utanför).
    """
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
        column = InfrastructureProject.geometry if bbox_column is None else bbox_column
        conditions.append(
            func.ST_Intersects(column, func.ST_MakeEnvelope(west, south, east, north, WGS84_SRID))
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
    """Förberäknade påverkanszoner: projektgeometrin buffrad med
    impact_radius_m i meter (via geography), för alla geometrityper —
    även linjer och ytor.

    Zonen ligger färdig i kolumnen impact_zone (en generated column som
    databasen räknar om vid varje skrivning, se modellen) — frågan
    serialiserar bara. Att buffra korridorerna per anrop kostade ~1,4 s.
    """
    conditions = _filter_conditions(
        statuses=statuses,
        project_types=project_types,
        bbox=bbox,
        year=year,
        bbox_column=InfrastructureProject.impact_zone,
    )
    conditions.append(InfrastructureProject.impact_zone.is_not(None))

    rows = await session.execute(
        select(
            InfrastructureProject.id,
            InfrastructureProject.name,
            InfrastructureProject.project_type,
            InfrastructureProject.status,
            InfrastructureProject.start_date,
            InfrastructureProject.end_date,
            InfrastructureProject.impact_radius_m,
            func.ST_AsGeoJSON(InfrastructureProject.impact_zone, GEOJSON_DECIMALER),
        )
        .where(*conditions)
        .order_by(InfrastructureProject.id)
    )

    features = [impact_zone_feature(*row) for row in rows.all()]
    return ImpactZoneCollection(features=features)


async def upsert_projects(
    session: AsyncSession, items: list[InfrastructureProjectIngest]
) -> tuple[int, int, int]:
    """Skriv in projekt från en datakälla. Returnerar (upserted, unchanged, skipped).

    Konflikthantering sker på external_id i en enda upsert per rad —
    inga N+1-läsfrågor. Varje rad skrivs i en savepoint så att ett
    enskilt trasigt objekt räknas som skipped i stället för att fälla
    hela synkroniseringen. Oförändrade rader rörs inte alls (WHERE-
    klausul på uppdateringen) — annars skulle updated_at flyttas fram
    vid varje omsynkning och tända falska notiser i bevakade områden.
    """
    upserted = 0
    unchanged = 0
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
            index_elements=[InfrastructureProject.external_id],
            set_=update_columns,
            where=changed_where(stmt, InfrastructureProject, values, conflict_key="external_id"),
        )
        try:
            async with session.begin_nested():
                result = await session.execute(stmt)
            # rowcount 0 = konflikt utan innehållsändring (WHERE föll) —
            # raden är oförändrad och updated_at har inte rörts.
            if result.rowcount:
                upserted += 1
            else:
                unchanged += 1
        except SQLAlchemyError:
            logger.warning(
                "Hoppar över projekt %s: databasfel vid upsert",
                item.external_id,
                exc_info=True,
            )
            skipped += 1

    return upserted, unchanged, skipped


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

    # Importeras här för att undvika cirkulär import — planning/demographics
    # importerar GEOJSON_DECIMALER från denna modul.
    from app.services import demographics as demographics_service
    from app.services import planning as planning_service

    # Loggraden committas INNAN hämtningen: en körning som dör i HTTP-lagret
    # ska ändå synas i synkloggen (med felet) — annars vet ingen att den
    # ens försökte. id och started_at läses ur INSERT-satsens RETURNING, inte
    # via refresh: en refresh efter commit öppnar en ny transaktion som
    # skulle hålla en poolad anslutning "idle in transaction" under hela den
    # (potentiellt minutlånga) hämtningen. Ingen transaktion ska vara öppen
    # medan vi väntar på nätverket.
    run = (
        await session.execute(insert(SyncRun).values(source=source_name).returning(SyncRun))
    ).scalar_one()
    await session.commit()
    run_id, started_at = run.id, run.started_at

    try:
        projects = await datasource.fetch_infrastructure_projects(bbox)
        properties = await datasource.fetch_properties(bbox)
        detail_plans = await datasource.fetch_detail_plans(bbox)
        deso_areas = await datasource.fetch_deso_areas(bbox)
    except DataSourceError as exc:
        await _finish_failed_run(session, run_id, str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except NotImplementedError as exc:
        await _finish_failed_run(session, run_id, str(exc))
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        # Oväntat fel (bugg, oinpackat nätverksfel) blir 500 som förut, men
        # loggraden stängs ändå — annars ser körningen ut att pågå för evigt.
        await _finish_failed_run(session, run_id, _unexpected_error_message(exc))
        raise

    try:
        project_counts = await upsert_projects(session, projects)
        property_counts = await property_service.upsert_properties(session, properties)
        plan_counts = await planning_service.upsert_detail_plans(session, detail_plans)
        deso_counts = await demographics_service.upsert_deso_areas(session, deso_areas)

        upserted, unchanged, skipped = (
            sum(counts)
            for counts in zip(
                project_counts, property_counts, plan_counts, deso_counts, strict=True
            )
        )
        fetched = len(projects) + len(properties) + len(detail_plans) + len(deso_areas)

        # Utfallet skrivs i SAMMA commit som datat — loggen kan aldrig påstå
        # att en synk lyckades om upserterna rullades tillbaka.
        run.fetched = fetched
        run.upserted = upserted
        run.unchanged = unchanged
        run.skipped = skipped
        run.truncated = datasource.truncated
        run.finished_at = func.now()
        await session.commit()
    except Exception as exc:
        # Databasfel som savepoint-logiken i upserterna inte fångar (tappad
        # anslutning, fel vid commit) rullar tillbaka datat — då ska
        # loggraden stängas med felet, inte stå kvar som "pågår".
        await _finish_failed_run(session, run_id, _unexpected_error_message(exc))
        raise

    return SyncResult(
        source=source_name,
        fetched=fetched,
        upserted=upserted,
        unchanged=unchanged,
        skipped=skipped,
        truncated=datasource.truncated,
        run_id=run_id,
        started_at=started_at,
    )


def _unexpected_error_message(exc: BaseException) -> str:
    """Kurerad text för synkloggen vid oväntade fel.

    Synkloggen läses utan skrivnyckel och visas ordagrant i lagerpanelen.
    SQLAlchemys felsträngar innehåller hela SQL-satsen med parametrar —
    det hör hemma i backendloggen, inte i ett öppet API. Datakällornas
    egna fel (DataSourceError) är handskrivna och sparas som de är.
    """
    logger.exception("Oväntat fel under synkronisering")
    return f"Oväntat fel ({type(exc).__name__}) — se backendloggen"


async def _finish_failed_run(session: AsyncSession, run_id: int, message: str) -> None:
    """Stäng loggraden med felet.

    Rullar tillbaka först: efter en misslyckad commit eller tappad
    anslutning vägrar sessionen allt annat tills dess (utan öppen
    transaktion är rollbacken ett no-op). Stängningen är en fristående
    UPDATE på id — raden är redan committad, så den fungerar oavsett vad
    rollbacken gjort med ORM-objektet (allt expireras). Misslyckas även
    stängningen (databasen borta) loggas det, och anroparen kastar sitt
    ursprungliga fel — ett databasfel får inte maskera källans 502.
    """
    try:
        await session.rollback()
        await session.execute(
            update(SyncRun)
            .where(SyncRun.id == run_id)
            .values(error=(message or "Okänt fel")[:500], finished_at=func.now())
            # Ingen läser ORM-objektet efteråt — hoppa över synkroniseringen av
            # identitetskartan (den skulle annars kosta en extra fråga).
            .execution_options(synchronize_session=False)
        )
        await session.commit()
    except Exception:
        logger.exception("Kunde inte stänga synkloggrad %s", run_id)


async def list_sync_runs(
    session: AsyncSession, *, source: str | None = None, limit: int = 20
) -> SyncRunList:
    """Senaste synkkörningarna, nyast först (id som tiebreak vid lika starttid).

    Med source hämtas bara den källans körningar — lagerpanelen frågar per
    källa, annars kan en flitigt synkad källa trycka ut en annans senaste
    körning ur fönstret.
    """
    stmt = select(SyncRun).order_by(SyncRun.started_at.desc(), SyncRun.id.desc()).limit(limit)
    if source is not None:
        stmt = stmt.where(SyncRun.source == source)
    rows = await session.execute(stmt)
    return SyncRunList(runs=[SyncRunInfo.model_validate(run) for run in rows.scalars()])
