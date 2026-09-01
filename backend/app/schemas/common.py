from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

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
    run_id: int = Field(description="Körningens id i synkloggen (GET /infrastructure/sync/runs)")
    started_at: datetime = Field(
        description="När körningen startade — tidsankare för 'Nytt sedan senast'"
    )


class SyncRunInfo(BaseModel):
    """En loggad synkkörning — alla kolumner i sync_runs."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    started_at: datetime
    finished_at: datetime | None = Field(
        default=None, description="null medan körningen pågår (eller om processen dog)"
    )
    fetched: int
    upserted: int
    unchanged: int
    skipped: int
    truncated: bool
    error: str | None = Field(default=None, description="Felmeddelande om körningen misslyckades")


class SyncRunList(BaseModel):
    runs: list[SyncRunInfo] = Field(
        default_factory=list, description="Senaste körningarna, nyast först"
    )
