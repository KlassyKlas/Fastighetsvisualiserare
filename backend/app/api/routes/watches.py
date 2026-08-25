from fastapi import APIRouter, HTTPException

from app.api.deps import SessionDep, WriteAccess
from app.schemas import (
    WatchedAreaCollection,
    WatchedAreaCreate,
    WatchedAreaFeature,
    WatchEventsResponse,
)
from app.services import watches as watches_service

router = APIRouter()


@router.get("/events", response_model=WatchEventsResponse)
async def watch_events(session: SessionDep) -> WatchEventsResponse:
    """Händelser i alla bevakade områden sedan de senast markerades som sedda.

    Nya och ändrade infrastrukturprojekt och detaljplaner som skär
    respektive område (ST_Intersects i PostGIS), plus totalräkning av
    vad som finns i området just nu.
    """
    return await watches_service.events(session)


@router.get("", response_model=WatchedAreaCollection)
async def list_watches(session: SessionDep) -> WatchedAreaCollection:
    """Alla bevakade områden som GeoJSON FeatureCollection."""
    return await watches_service.list_watches(session)


@router.post("", response_model=WatchedAreaFeature, status_code=201, dependencies=[WriteAccess])
async def create_watch(session: SessionDep, data: WatchedAreaCreate) -> WatchedAreaFeature:
    """Skapa ett bevakat område från en ritad polygon."""
    return await watches_service.create_watch(session, data)


@router.delete("/{watch_id}", status_code=204, dependencies=[WriteAccess])
async def delete_watch(session: SessionDep, watch_id: int) -> None:
    deleted = await watches_service.delete_watch(session, watch_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Bevakningen hittades inte")


@router.post(
    "/{watch_id}/mark-seen",
    response_model=WatchedAreaFeature,
    dependencies=[WriteAccess],
)
async def mark_watch_seen(session: SessionDep, watch_id: int) -> WatchedAreaFeature:
    """Markera områdets händelser som sedda (flyttar fram last_seen_at)."""
    feature = await watches_service.mark_seen(session, watch_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Bevakningen hittades inte")
    return feature
