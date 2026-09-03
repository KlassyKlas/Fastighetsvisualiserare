from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    BigInteger,
    Computed,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# Påverkanszonen lagras färdigräknad: projektgeometrin buffrad med
# impact_radius_m meter över geography (rätt för punkter, linjer och ytor
# oavsett latitud) och förenklad med ~20 m tolerans (0,0002 grader) — en
# buffrad korridor har annars tiotusentals hörn. Zonen är en visuell
# hjälpyta för kartlagret; analysfrågorna räknar exakt med ST_DWithin över
# geography och rör den inte.
#
# Kolumnen är en STORED generated column: databasen räknar om zonen när
# geometry eller impact_radius_m skrivs, oavsett skrivväg (synk, API,
# skript, handskriven SQL) — det finns ingen appkod som kan glömma den.
# ST_Buffer(geography, float8) är IMMUTABLE i PostGIS, vilket generated
# columns kräver. Samma uttryck står ordagrant i migration 0005; ändras
# det (t.ex. toleransen) krävs en ny migration som droppar och återskapar
# kolumnen — alembic check varnar om modell och databas glider isär.
IMPACT_ZONE_SQL = (
    "ST_SimplifyPreserveTopology(ST_Buffer(geometry::geography, impact_radius_m)::geometry, 0.0002)"
)


class InfrastructureProject(Base):
    __tablename__ = "infrastructure_projects"
    __table_args__ = (
        # Se kommentaren i Property — krävs för att geography-frågorna
        # (påverkanszoner, närhetsanalys) ska kunna använda index.
        Index(
            "idx_infrastructure_projects_geometry_geog",
            text("CAST(geometry AS geography(GEOMETRY,4326))"),
            postgresql_using="gist",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(String, unique=True, index=True)
    # Datakällans namn: "trafikverket", "kommun", "manual", ...
    source: Mapped[str] = mapped_column(String, index=True, default="manual")
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    # Värden ur app.domain.ProjectType — valideras i schemalagret
    project_type: Mapped[str | None] = mapped_column(String, index=True)
    # Värden ur app.domain.ProjectStatus — valideras i schemalagret
    status: Mapped[str | None] = mapped_column(String, index=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    budget_sek: Mapped[int | None] = mapped_column(BigInteger)
    # Punkter, linjer och ytor förekommer alla — därför generisk GEOMETRY.
    geometry: Mapped[WKBElement | None] = mapped_column(
        Geometry("GEOMETRY", srid=4326), nullable=True
    )
    impact_radius_m: Mapped[float] = mapped_column(Float, default=1000.0)
    # Se IMPACT_ZONE_SQL. deferred: zonpolygonerna är stora (megabyte för
    # korridorer) och får inte följa med varje select(InfrastructureProject)
    # — bara påverkanszonsfrågan läser kolumnen, uttryckligen.
    impact_zone: Mapped[WKBElement | None] = mapped_column(
        Geometry("GEOMETRY", srid=4326),
        Computed(IMPACT_ZONE_SQL, persisted=True),
        nullable=True,
        deferred=True,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<InfrastructureProject(id={self.id}, name='{self.name}', status='{self.status}')>"
