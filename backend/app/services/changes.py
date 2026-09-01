"""Nytt sedan senast: nya och ändrade projekt och detaljplaner i hela datamängden.

Bevakningarna (services/watches.py) svarar per ritat område; den här
tjänsten svarar globalt sedan en tidpunkt — användarens senaste besök
eller senaste synk. Räkningarna görs i SQL så att total_events stämmer
även när händelselistan trunkeras av limit.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import Select, and_, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import WatchEventKind
from app.models import DetailPlan, InfrastructureProject
from app.schemas import ChangesResponse, DetailPlanWatchEvent, ProjectWatchEvent
from app.services.infrastructure import GEOJSON_DECIMALER
from app.services.serializers import detail_plan_feature, project_feature

# Båda lagren har created_at/updated_at/id/geometry — det är allt frågorna rör.
EventModel = type[InfrastructureProject] | type[DetailPlan]


def ensure_utc(value: datetime) -> datetime:
    """Gör tidpunkten tz-medveten i UTC.

    asyncpg vägrar binda naiva datetime mot timestamptz. En naiv "since"
    från klienten tolkas som UTC (JavaScript:s toISOString ger alltid
    UTC); en tidszonsatt tidpunkt räknas om till UTC så att svaret ekar
    samma form oavsett hur klienten skrev den.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def classify_event(
    created_at: datetime | None,
    updated_at: datetime | None,
    seen_at: datetime,
) -> WatchEventKind | None:
    """Avgör om ett objekt är en händelse sedan seen_at — och vilken sort.

    Skapat efter seen_at räknas som nytt; enbart uppdaterat efter
    seen_at räknas som ändrat. Objekt utan tidsstämplar ger ingen
    händelse (de kan inte placeras i tiden). Regeln delas med
    bevakningarna, och SQL-räkningarna i _count_events speglar den exakt.
    """
    if created_at is not None and created_at > seen_at:
        return WatchEventKind.NYTT
    if updated_at is not None and updated_at > seen_at:
        return WatchEventKind.ANDRAT
    return None


def take_with_overflow[T](rows: Sequence[T], budget: int) -> tuple[list[T], bool]:
    """De första `budget` raderna, och om det fanns fler.

    Frågorna hämtar budget + 1 rader: den extra raden avslöjar
    trunkering utan en separat räkning per lista. Med budget 0 hämtas
    ändå en rad — enbart för att kunna sätta truncated.
    """
    return list(rows[:budget]), len(rows) > budget


def _event_rows(model: EventModel, since: datetime) -> Select[tuple[object, str | None]]:
    """Nya eller ändrade rader sedan since, senast ändrade först."""
    return (
        select(model, func.ST_AsGeoJSON(model.geometry, GEOJSON_DECIMALER))
        .where(or_(model.created_at > since, model.updated_at > since))
        .order_by(model.updated_at.desc(), model.id.desc())
    )


async def _count_events(
    session: AsyncSession, model: EventModel, since: datetime
) -> tuple[int, int]:
    """(nya, ändrade) sedan since — räknat i SQL med FILTER-klausuler.

    Nytt = skapat efter since; ändrat = uppdaterat efter since men inte
    skapat efter since. Summan är därmed exakt antalet rader som
    _event_rows matchar, oberoende av limit.
    """
    is_new = model.created_at > since
    is_changed = and_(model.updated_at > since, not_(is_new))
    new_count, changed_count = (
        await session.execute(
            select(func.count().filter(is_new), func.count().filter(is_changed)).select_from(model)
        )
    ).one()
    return int(new_count or 0), int(changed_count or 0)


async def changes(session: AsyncSession, *, since: datetime, limit: int = 200) -> ChangesResponse:
    """Händelser och räkningar i hela datamängden sedan `since`.

    Fördelning av limit: projekten fyller listan först (senast ändrade
    först), detaljplanerna får det som blir över. Valet är medvetet
    enkelt — projekten är få (tiotal–hundratal) medan en
    detaljplanesynk kan ge tusentals rader, och en förutsägbar ordning
    är lättare att förklara i gränssnittet än en proportionell
    fördelning. Räkningarna påverkas inte av limit.
    """
    since = ensure_utc(since)

    project_new, project_changed = await _count_events(session, InfrastructureProject, since)
    plan_new, plan_changed = await _count_events(session, DetailPlan, since)

    project_rows = (
        await session.execute(_event_rows(InfrastructureProject, since).limit(limit + 1))
    ).all()
    projects, projects_overflow = take_with_overflow(project_rows, limit)

    remaining = limit - len(projects)
    plan_rows = (await session.execute(_event_rows(DetailPlan, since).limit(remaining + 1))).all()
    plans, plans_overflow = take_with_overflow(plan_rows, remaining)

    # WHERE-villkoret garanterar att classify_event ger en sort — walrus-
    # filtret finns bara för typsäkerheten (samma mönster som watches).
    project_events = [
        ProjectWatchEvent(event_kind=kind, project=project_feature(project, geojson))
        for project, geojson in projects
        if (kind := classify_event(project.created_at, project.updated_at, since))
    ]
    plan_events = [
        DetailPlanWatchEvent(event_kind=kind, plan=detail_plan_feature(plan, geojson))
        for plan, geojson in plans
        if (kind := classify_event(plan.created_at, plan.updated_at, since))
    ]

    return ChangesResponse(
        since=since,
        project_events=project_events,
        plan_events=plan_events,
        project_new=project_new,
        project_changed=project_changed,
        plan_new=plan_new,
        plan_changed=plan_changed,
        total_events=project_new + project_changed + plan_new + plan_changed,
        truncated=projects_overflow or plans_overflow,
    )
