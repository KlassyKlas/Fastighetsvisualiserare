from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain import PropertyType
from app.schemas.common import GeoJSONGeometry


class PropertyProps(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    designation: str
    municipality: str | None = None
    county: str | None = None
    area_sqm: float | None = None
    assessed_value_sek: int | None = None
    property_type: PropertyType | None = None
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


class PropertyFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONGeometry | None = None
    properties: PropertyProps


class PropertyCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[PropertyFeature] = Field(default_factory=list)
    # OGC API Features-inspirerade metadatafält för paginering
    numberMatched: int = Field(description="Totalt antal träffar för frågan")
    numberReturned: int = Field(description="Antal features i detta svar")


class PropertyCreate(BaseModel):
    designation: str = Field(min_length=1)
    municipality: str | None = None
    county: str | None = None
    area_sqm: float | None = Field(default=None, ge=0)
    assessed_value_sek: int | None = Field(default=None, ge=0)
    property_type: PropertyType | None = None
    owner_name: str | None = None
    owner_org_number: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    geometry: GeoJSONGeometry | None = Field(
        default=None, description="GeoJSON-geometri (Polygon eller MultiPolygon) i WGS84"
    )
    building_year: int | None = Field(default=None, ge=1000, le=2200)
    living_area_sqm: float | None = Field(default=None, ge=0)
    zoning: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
