from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import BigInteger, DateTime, Float, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Property(Base):
    __tablename__ = "properties"
    __table_args__ = (
        # Analysfrågorna (ST_DWithin/ST_Distance) castar till geography —
        # utan funktionellt index används GiST-indexet på geometry inte alls.
        # Uttrycket måste vara EXAKT detsamma som frågorna genererar
        # (Geography(srid=4326) → geography(GEOMETRY,4326)) för att
        # planeraren ska kunna använda indexet.
        Index(
            "idx_properties_geometry_geog",
            text("CAST(geometry AS geography(GEOMETRY,4326))"),
            postgresql_using="gist",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Fastighetsbeteckning, t.ex. "Norrmalm 1:5"
    designation: Mapped[str] = mapped_column(String, unique=True, index=True)
    municipality: Mapped[str | None] = mapped_column(String, index=True)
    county: Mapped[str | None] = mapped_column(String)
    area_sqm: Mapped[float | None] = mapped_column(Float)
    assessed_value_sek: Mapped[int | None] = mapped_column(BigInteger)
    property_type: Mapped[str | None] = mapped_column(String, index=True)
    owner_name: Mapped[str | None] = mapped_column(String)
    owner_org_number: Mapped[str | None] = mapped_column(String)
    address: Mapped[str | None] = mapped_column(String)
    postal_code: Mapped[str | None] = mapped_column(String)
    city: Mapped[str | None] = mapped_column(String)
    # Fastigheter kan bestå av flera skiften — därför MULTIPOLYGON.
    # Enkla polygoner konverteras vid skrivning (se app.services.geo).
    geometry: Mapped[WKBElement | None] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326), nullable=True
    )
    building_year: Mapped[int | None] = mapped_column(Integer)
    living_area_sqm: Mapped[float | None] = mapped_column(Float)
    zoning: Mapped[str | None] = mapped_column(String)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Property(id={self.id}, designation='{self.designation}')>"
