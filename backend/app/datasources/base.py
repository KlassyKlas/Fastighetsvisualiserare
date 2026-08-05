"""Grundkontrakt för externa datakällor.

En datakälla registreras med ``@register`` och blir då automatiskt
tillgänglig via ``POST /api/v1/infrastructure/sync/{källnamn}``.
Datakällor returnerar typade ingest-modeller — aldrig råa dictar —
så att fel i extern data upptäcks vid parsning, inte vid skrivning.
"""

from abc import ABC
from datetime import date
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from app.domain import ProjectStatus, ProjectType
from app.schemas.common import GeoJSONGeometry
from app.schemas.property import PropertyCreate

Bbox = tuple[float, float, float, float]
"""(väst, syd, öst, norr) i WGS84."""


class DataSourceError(RuntimeError):
    """Fel vid hämtning från en extern datakälla.

    Görs alltid synligt för anroparen (HTTP 502) — tysta fel döljer
    trasiga integrationer.
    """

    def __init__(self, source: str, message: str) -> None:
        self.source = source
        super().__init__(f"[{source}] {message}")


class UnknownDataSourceError(KeyError):
    def __init__(self, name: str, available: list[str]) -> None:
        self.name = name
        self.available = available
        super().__init__(name)


class InfrastructureProjectIngest(BaseModel):
    """Typat kontrakt för infrastrukturprojekt från externa källor."""

    external_id: str = Field(min_length=1)
    source: str
    name: str = Field(min_length=1)
    description: str | None = None
    project_type: ProjectType = ProjectType.OVRIGT
    status: ProjectStatus = ProjectStatus.PAGAENDE
    start_date: date | None = None
    end_date: date | None = None
    budget_sek: int | None = Field(default=None, ge=0)
    geometry: GeoJSONGeometry | None = None
    impact_radius_m: float = Field(default=1000.0, gt=0, le=50_000)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


# Fastighetsdata från externa källor har samma form som API:ts create-schema.
PropertyIngest = PropertyCreate


class DetailPlanIngest(BaseModel):
    """Typat kontrakt för detaljplaner från externa källor (Lantmäteriet NGP)."""

    external_id: str = Field(min_length=1)
    source: str
    name: str = Field(min_length=1)
    plan_number: str | None = None
    status: str | None = None
    municipality: str | None = None
    purpose: str | None = None
    adopted_date: date | None = None
    geometry: GeoJSONGeometry | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class DesoAreaIngest(BaseModel):
    """Typat kontrakt för DeSO-områden med demografi (SCB)."""

    deso_code: str = Field(min_length=1)
    municipality_code: str | None = None
    municipality: str | None = None
    population: int | None = Field(default=None, ge=0)
    population_year: int | None = None
    mean_income_sek: int | None = Field(default=None, ge=0)
    higher_education_share: float | None = Field(default=None, ge=0, le=1)
    geometry: GeoJSONGeometry | None = None
    stats_json: dict[str, Any] = Field(default_factory=dict)


class DataSource(ABC):
    """Bas för externa datakällor.

    Underklasser sätter ``name`` (används i sync-URL:en) och överlagrar
    de fetch-metoder källan faktiskt stödjer. Standardimplementationerna
    returnerar tomma listor så att en källa bara behöver implementera
    det den levererar.
    """

    name: ClassVar[str]
    display_name: ClassVar[str] = ""

    #: Sätts av en fetch-metod om källan inte kunde hämta allt (t.ex.
    #: sidgräns nådd). Läses av sync-tjänsten och exponeras i SyncResult.
    truncated: bool = False

    async def fetch_infrastructure_projects(
        self, bbox: Bbox | None = None
    ) -> list[InfrastructureProjectIngest]:
        return []

    async def fetch_properties(self, bbox: Bbox | None = None) -> list[PropertyIngest]:
        return []

    async def fetch_detail_plans(self, bbox: Bbox | None = None) -> list[DetailPlanIngest]:
        return []

    async def fetch_deso_areas(self, bbox: Bbox | None = None) -> list[DesoAreaIngest]:
        return []


_registry: dict[str, type[DataSource]] = {}


def register(cls: type[DataSource]) -> type[DataSource]:
    """Klassdekorator som gör en datakälla tillgänglig för synkronisering."""
    _registry[cls.name] = cls
    return cls


def get_datasource(name: str) -> DataSource:
    try:
        return _registry[name]()
    except KeyError:
        raise UnknownDataSourceError(name, sorted(_registry)) from None


def available_sources() -> dict[str, str]:
    """Registrerade källor: namn → visningsnamn."""
    return {name: cls.display_name or name for name, cls in sorted(_registry.items())}
