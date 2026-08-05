from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.connection import Base


class InfrastructureProject(Base):
    __tablename__ = "infrastructure_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(
        String, unique=True, index=True, nullable=True
    )
    source: Mapped[str] = mapped_column(
        String, index=True, default="manual"
    )  # "trafikverket", "kommun", "manual"
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_type: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # "väg", "järnväg", "kollektivtrafik", "bro", "tunnel", "cykelväg", "övrigt"
    status: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # "planerad", "pågående", "avslutad"
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    budget_sek: Mapped[float | None] = mapped_column(Float, nullable=True)
    geometry = mapped_column(Geometry("GEOMETRY", srid=4326), nullable=True)
    impact_radius_m: Mapped[float] = mapped_column(Float, default=1000.0)
    metadata_json = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<InfrastructureProject(id={self.id}, name='{self.name}', status='{self.status}')>"
