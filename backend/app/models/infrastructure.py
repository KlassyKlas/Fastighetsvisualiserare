from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    BigInteger,
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


class InfrastructureProject(Base):
    __tablename__ = "infrastructure_projects"
    __table_args__ = (
        # Se kommentaren i Property — krävs för att geography-frågorna
        # (påverkanszoner, närhetsanalys) ska kunna använda index.
        Index(
            "idx_infrastructure_projects_geometry_geog",
            text("CAST(geometry AS geography)"),
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
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<InfrastructureProject(id={self.id}, name='{self.name}', status='{self.status}')>"
