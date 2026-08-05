from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PropertyProperties(BaseModel):
    id: int
    designation: str
    municipality: str | None = None
    county: str | None = None
    area_sqm: float | None = None
    assessed_value_sek: float | None = None
    property_type: str | None = None
    owner_name: str | None = None
    owner_org_number: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    building_year: int | None = None
    living_area_sqm: float | None = None
    zoning: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PropertyFeature(BaseModel):
    type: str = "Feature"
    geometry: dict | None = None
    properties: PropertyProperties


class PropertyCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[PropertyFeature] = Field(default_factory=list)


class PropertyCreate(BaseModel):
    designation: str
    municipality: str | None = None
    county: str | None = None
    area_sqm: float | None = None
    assessed_value_sek: float | None = None
    property_type: str | None = None
    owner_name: str | None = None
    owner_org_number: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    geometry: dict | None = None  # GeoJSON geometry
    building_year: int | None = None
    living_area_sqm: float | None = None
    zoning: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
