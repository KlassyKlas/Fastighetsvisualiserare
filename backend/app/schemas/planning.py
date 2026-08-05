from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import GeoJSONGeometry


class DetailPlanProps(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    source: str = "detaljplaner"
    name: str
    plan_number: str | None = None
    # Boverkets planstatus som fri sträng ("gällande", "pågående", ...) —
    # värdemängden ägs av källan, inte av vårt kontrakt.
    status: str | None = None
    municipality: str | None = None
    purpose: str | None = None
    adopted_date: date | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DetailPlanFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONGeometry | None = None
    properties: DetailPlanProps


class DetailPlanCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[DetailPlanFeature] = Field(default_factory=list)
    numberMatched: int = Field(description="Totalt antal träffar för frågan")
    numberReturned: int = Field(description="Antal features i detta svar")
