from typing import Any, Literal

from pydantic import BaseModel, Field

# GeoJSON-geometrier valideras av shapely vid skrivning och produceras av
# PostGIS (ST_AsGeoJSON) vid läsning — här typas de medvetet löst.
# Frontendens GeoJSON-typer kommer från @types/geojson.
GeoJSONGeometry = dict[str, Any]


class HealthStatus(BaseModel):
    # Vid databasfel svarar endpointen 503 — "database" kan därför bara
    # vara "ok" i ett lyckat svar.
    status: Literal["ok"] = "ok"
    database: Literal["ok"] = "ok"
    version: str


class SyncResult(BaseModel):
    """Resultatet av en synkronisering mot en extern datakälla."""

    source: str
    fetched: int = Field(description="Antal objekt som datakällan levererade")
    upserted: int = Field(description="Antal objekt som skapades eller faktiskt ändrades")
    unchanged: int = Field(
        default=0,
        description="Antal objekt som var identiska med databasen och lämnades orörda",
    )
    skipped: int = Field(description="Antal objekt som hoppades över (t.ex. ogiltig geometri)")
    truncated: bool = Field(
        default=False,
        description="true om källan inte kunde hämta allt (sidgräns nådd) — kör synken igen",
    )
