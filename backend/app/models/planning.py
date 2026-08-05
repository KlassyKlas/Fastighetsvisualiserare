from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import Date, DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DetailPlan(Base):
    """Detaljplan ur Lantmäteriets nationella geodataplattform (NGP).

    Status lagras som fri sträng (Boverkets planstatusvärden varierar
    mellan leveranser) — färgsättning och etiketter hanteras i frontend
    med reservfärg för okända värden.
    """

    __tablename__ = "detail_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # NGP:s objektidentitet (UUID) — stabil nyckel för upsert.
    external_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    source: Mapped[str] = mapped_column(String, index=True, default="detaljplaner")
    name: Mapped[str] = mapped_column(String)
    # Kommunal planbeteckning, t.ex. "Dp 2019-01234"
    plan_number: Mapped[str | None] = mapped_column(String)
    status: Mapped[str | None] = mapped_column(String, index=True)
    municipality: Mapped[str | None] = mapped_column(String, index=True)
    purpose: Mapped[str | None] = mapped_column(Text)
    # Datum då planen vann laga kraft (eller antogs, om laga kraft saknas)
    adopted_date: Mapped[date | None] = mapped_column(Date)
    geometry: Mapped[WKBElement | None] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326), nullable=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<DetailPlan(id={self.id}, name='{self.name}', status='{self.status}')>"
