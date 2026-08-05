from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import DateTime, Float, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DesoArea(Base):
    """Demografiskt statistikområde (DeSO) med SCB-statistik.

    Gränserna kommer från SCB:s öppna geodata och statistiken från
    PXWeb-API:t. De metriker som driver choropleth-lagret ligger som
    egna kolumner; övrig statistik samlas utbyggbart i stats_json.
    """

    __tablename__ = "deso_areas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # DeSO-kod, t.ex. "0180C1180" (kommunkod + tätortsklass + löpnummer)
    deso_code: Mapped[str] = mapped_column(String, unique=True, index=True)
    municipality_code: Mapped[str | None] = mapped_column(String, index=True)
    municipality: Mapped[str | None] = mapped_column(String, index=True)
    population: Mapped[int | None] = mapped_column(Integer)
    # Årtal som befolknings- och inkomstuppgifterna avser
    population_year: Mapped[int | None] = mapped_column(Integer)
    # Medelvärde av nettoinkomst (SCB publicerar ingen median på DeSO-nivå)
    mean_income_sek: Mapped[int | None] = mapped_column(Integer)
    # Andel 25–64 år med eftergymnasial utbildning (0–1)
    higher_education_share: Mapped[float | None] = mapped_column(Float)
    geometry: Mapped[WKBElement | None] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326), nullable=True
    )
    stats_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<DesoArea(id={self.id}, deso_code='{self.deso_code}')>"
