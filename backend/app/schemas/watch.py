from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain import WatchEventKind
from app.schemas.common import GeoJSONGeometry
from app.schemas.infrastructure import InfrastructureProjectFeature
from app.schemas.planning import DetailPlanFeature


class WatchedAreaProps(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    last_seen_at: datetime | None = Field(
        default=None, description="När användaren senast markerade händelserna som sedda"
    )
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WatchedAreaFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONGeometry | None = None
    properties: WatchedAreaProps


class WatchedAreaCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[WatchedAreaFeature] = Field(default_factory=list)
    numberMatched: int = Field(description="Totalt antal bevakade områden")
    numberReturned: int = Field(description="Antal features i detta svar")


class WatchedAreaCreate(BaseModel):
    name: str = Field(min_length=1)
    geometry: GeoJSONGeometry = Field(
        description="GeoJSON-geometri (Polygon eller MultiPolygon) i WGS84"
    )


class ProjectWatchEvent(BaseModel):
    """Ett infrastrukturprojekt som tillkommit/ändrats i ett bevakat område."""

    event_kind: WatchEventKind
    project: InfrastructureProjectFeature


class DetailPlanWatchEvent(BaseModel):
    """En detaljplan som tillkommit/ändrats i ett bevakat område."""

    event_kind: WatchEventKind
    plan: DetailPlanFeature


class WatchEvents(BaseModel):
    """Händelserna för ett bevakat område sedan senaste "markera som sett"."""

    watch_id: int
    watch_name: str
    last_seen_at: datetime | None = None
    project_count: int = Field(description="Totalt antal projekt som skär området")
    plan_count: int = Field(description="Totalt antal detaljplaner som skär området")
    project_events: list[ProjectWatchEvent] = Field(default_factory=list)
    plan_events: list[DetailPlanWatchEvent] = Field(default_factory=list)


class WatchEventsResponse(BaseModel):
    watches: list[WatchEvents] = Field(default_factory=list)
    total_events: int = Field(description="Summan av händelser över alla bevakade områden")
