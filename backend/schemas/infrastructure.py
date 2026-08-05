from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InfrastructureProjectProperties(BaseModel):
    id: int
    external_id: str | None = None
    source: str = "manual"
    name: str
    description: str | None = None
    project_type: str | None = None
    status: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    budget_sek: float | None = None
    impact_radius_m: float = 1000.0
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class InfrastructureProjectFeature(BaseModel):
    type: str = "Feature"
    geometry: dict | None = None
    properties: InfrastructureProjectProperties


class InfrastructureProjectCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[InfrastructureProjectFeature] = Field(default_factory=list)


class InfrastructureProjectCreate(BaseModel):
    external_id: str | None = None
    source: str = "manual"
    name: str
    description: str | None = None
    project_type: str | None = None
    status: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    budget_sek: float | None = None
    geometry: dict | None = None  # GeoJSON geometry
    impact_radius_m: float = 1000.0
    metadata_json: dict[str, Any] = Field(default_factory=dict)
