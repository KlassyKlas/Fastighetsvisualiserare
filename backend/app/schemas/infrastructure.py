from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain import ProjectStatus, ProjectType
from app.schemas.common import GeoJSONGeometry


class InfrastructureProjectProps(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str | None = None
    source: str = "manual"
    name: str
    description: str | None = None
    project_type: ProjectType | None = None
    status: ProjectStatus | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget_sek: int | None = None
    impact_radius_m: float = 1000.0
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InfrastructureProjectFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONGeometry | None = None
    properties: InfrastructureProjectProps


class InfrastructureProjectCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[InfrastructureProjectFeature] = Field(default_factory=list)
    numberMatched: int = Field(description="Totalt antal träffar för frågan")
    numberReturned: int = Field(description="Antal features i detta svar")


class InfrastructureProjectCreate(BaseModel):
    external_id: str | None = None
    source: str = "manual"
    name: str = Field(min_length=1)
    description: str | None = None
    project_type: ProjectType | None = None
    status: ProjectStatus | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget_sek: int | None = Field(default=None, ge=0)
    geometry: GeoJSONGeometry | None = Field(default=None, description="GeoJSON-geometri i WGS84")
    impact_radius_m: float = Field(default=1000.0, gt=0, le=50_000)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ImpactZoneProps(BaseModel):
    """Egenskaper för en serverberäknad påverkanszon (buffrad projektgeometri)."""

    project_id: int
    name: str
    project_type: ProjectType | None = None
    status: ProjectStatus | None = None
    start_date: date | None = None
    end_date: date | None = None
    impact_radius_m: float


class ImpactZoneFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONGeometry | None = None
    properties: ImpactZoneProps


class ImpactZoneCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[ImpactZoneFeature] = Field(default_factory=list)
