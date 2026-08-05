from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import GeoJSONGeometry


class DesoAreaProps(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    deso_code: str
    municipality_code: str | None = None
    municipality: str | None = None
    population: int | None = None
    population_year: int | None = None
    mean_income_sek: int | None = Field(
        default=None, description="Medelvärde av nettoinkomst, kr/år (SCB har ingen DeSO-median)"
    )
    higher_education_share: float | None = Field(
        default=None, description="Andel 25–64 år med eftergymnasial utbildning (0–1)"
    )
    area_km2: float | None = Field(
        default=None, description="Landyta beräknad ur geometrin (PostGIS geography)"
    )
    population_density: float | None = Field(
        default=None, description="Invånare per km², beräknad ur population och area_km2"
    )
    stats_json: dict[str, Any] = Field(default_factory=dict)


class DesoAreaFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONGeometry | None = None
    properties: DesoAreaProps


class DesoAreaCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[DesoAreaFeature] = Field(default_factory=list)
    numberMatched: int = Field(description="Totalt antal träffar för frågan")
    numberReturned: int = Field(description="Antal features i detta svar")
