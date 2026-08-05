from typing import Any, Literal

from pydantic import BaseModel, Field

# GeoJSON-geometrier valideras av shapely vid skrivning och produceras av
# PostGIS (ST_AsGeoJSON) vid läsning — här typas de medvetet löst.
# Frontendens GeoJSON-typer kommer från @types/geojson.
GeoJSONGeometry = dict[str, Any]


class HealthStatus(BaseModel):
    status: Literal["ok"] = "ok"
    database: Literal["ok", "unavailable"]
    version: str


class SyncResult(BaseModel):
    """Resultatet av en synkronisering mot en extern datakälla."""

    source: str
    fetched: int = Field(description="Antal objekt som datakällan levererade")
    upserted: int = Field(description="Antal objekt som skapades eller uppdaterades")
    skipped: int = Field(description="Antal objekt som hoppades över (t.ex. utan externt id)")
