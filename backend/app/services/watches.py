"""Bevakade områden: CRUD och händelsefråga.

Ett bevakat område är en användarritad polygon. Händelsefrågan svarar
på "vad har hänt i mina områden sedan jag senast tittade?" — nya och
ändrade infrastrukturprojekt och detaljplaner som skär området, avgjort
med ST_Intersects i PostGIS (ren geometrioperation, inga meter).
"""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import WatchEventKind
from app.models import DetailPlan, InfrastructureProject, WatchedArea
from app.schemas import (
    DetailPlanWatchEvent,
    ProjectWatchEvent,
    WatchedAreaCollection,
    WatchedAreaCreate,
    WatchedAreaFeature,
    WatchedAreaProps,
    WatchEvents,
    WatchEventsResponse,
)
from app.services.geo import geojson_to_element, parse_geojson_column
from app.services.infrastructure import GEOJSON_DECIMALER
from app.services.serializers import detail_plan_feature, project_feature


def classify_event(
    created_at: datetime | None,
    updated_at: datetime | None,
    seen_at: datetime,
) -> WatchEventKind | None:
    """Avgör om ett objekt är en händelse sedan seen_at — och vilken sort.

    Skapat efter seen_at räknas som nytt; enbart uppdaterat efter
    seen_at räknas som ändrat. Objekt utan tidsstämplar ger ingen
    händelse (de kan inte placeras i tiden).
    """
    if created_at is not None and created_at > seen_at:
        return WatchEventKind.NYTT
    if updated_at is not None and updated_at > seen_at:
        return WatchEventKind.ANDRAT
    return None


def _watched_area_feature(watch: WatchedArea, geojson: str | None) -> WatchedAreaFeature:
    return WatchedAreaFeature(
        geometry=parse_geojson_column(geojson),
        properties=WatchedAreaProps.model_validate(watch),
    )


async def list_watches(session: AsyncSession) -> WatchedAreaCollection:
    rows = await session.execute(
        select(WatchedArea, func.ST_AsGeoJSON(WatchedArea.geometry, GEOJSON_DECIMALER)).order_by(
            WatchedArea.id
        )
    )
    features = [_watched_area_feature(watch, geojson) for watch, geojson in rows.all()]
    return WatchedAreaCollection(
        features=features,
        numberMatched=len(features),
        numberReturned=len(features),
    )


async def create_watch(session: AsyncSession, data: WatchedAreaCreate) -> WatchedAreaFeature:
    try:
        geometry = geojson_to_element(data.geometry, allowed_types=("MultiPolygon",))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # En ny bevakning börjar "ren": bara det som händer EFTER skapandet
    # räknas som händelser — annars skulle hela befintliga datamängden
    # dyka upp som olästa notiser direkt.
    watch = WatchedArea(name=data.name, geometry=geometry, last_seen_at=func.now())
    session.add(watch)
    await session.commit()
    await session.refresh(watch)

    geojson = await session.scalar(
        select(func.ST_AsGeoJSON(WatchedArea.geometry, GEOJSON_DECIMALER)).where(
            WatchedArea.id == watch.id
        )
    )
    return _watched_area_feature(watch, geojson)


async def delete_watch(session: AsyncSession, watch_id: int) -> bool:
    watch = await session.get(WatchedArea, watch_id)
    if watch is None:
        return False
    await session.delete(watch)
    await session.commit()
    return True


async def mark_seen(session: AsyncSession, watch_id: int) -> WatchedAreaFeature | None:
    watch = await session.get(WatchedArea, watch_id)
    if watch is None:
        return None
    watch.last_seen_at = func.now()
    await session.commit()
    await session.refresh(watch)

    geojson = await session.scalar(
        select(func.ST_AsGeoJSON(WatchedArea.geometry, GEOJSON_DECIMALER)).where(
            WatchedArea.id == watch.id
        )
    )
    return _watched_area_feature(watch, geojson)


async def events(session: AsyncSession) -> WatchEventsResponse:
    """Händelser och innehållsräkning för samtliga bevakade områden.

    Antalet bevakningar är litet (användarritade) — en intersect-fråga
    per bevakning och datalager är enklare och tillräckligt snabb.
    """
    watches = (await session.execute(select(WatchedArea).order_by(WatchedArea.id))).scalars().all()

    result: list[WatchEvents] = []
    total_events = 0

    for watch in watches:
        # last_seen_at sätts vid skapandet, men skydda mot NULL (t.ex.
        # rader skrivna utanför API:t) genom att falla tillbaka på
        # skapandetidpunkten.
        seen_at = watch.last_seen_at or watch.created_at

        # watch.geometry (WKBElement) binds som parameter — ingen join
        # mot watched_areas behövs i intersect-frågorna.
        project_rows = await session.execute(
            select(
                InfrastructureProject,
                func.ST_AsGeoJSON(InfrastructureProject.geometry, GEOJSON_DECIMALER),
            )
            .where(
                InfrastructureProject.geometry.is_not(None),
                func.ST_Intersects(InfrastructureProject.geometry, watch.geometry),
            )
            .order_by(InfrastructureProject.updated_at.desc())
        )
        plan_rows = await session.execute(
            select(DetailPlan, func.ST_AsGeoJSON(DetailPlan.geometry, GEOJSON_DECIMALER))
            .where(
                DetailPlan.geometry.is_not(None),
                func.ST_Intersects(DetailPlan.geometry, watch.geometry),
            )
            .order_by(DetailPlan.updated_at.desc())
        )

        projects = project_rows.all()
        plans = plan_rows.all()

        project_events = [
            ProjectWatchEvent(event_kind=kind, project=project_feature(project, geojson))
            for project, geojson in projects
            if (kind := classify_event(project.created_at, project.updated_at, seen_at))
        ]
        plan_events = [
            DetailPlanWatchEvent(event_kind=kind, plan=detail_plan_feature(plan, geojson))
            for plan, geojson in plans
            if (kind := classify_event(plan.created_at, plan.updated_at, seen_at))
        ]

        total_events += len(project_events) + len(plan_events)
        result.append(
            WatchEvents(
                watch_id=watch.id,
                watch_name=watch.name,
                last_seen_at=watch.last_seen_at,
                project_count=len(projects),
                plan_count=len(plans),
                project_events=project_events,
                plan_events=plan_events,
            )
        )

    return WatchEventsResponse(watches=result, total_events=total_events)
