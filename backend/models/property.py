from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.connection import Base


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    designation: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )  # fastighetsbeteckning
    municipality: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    county: Mapped[str | None] = mapped_column(String, nullable=True)
    area_sqm: Mapped[float | None] = mapped_column(Float, nullable=True)
    assessed_value_sek: Mapped[float | None] = mapped_column(Float, nullable=True)
    property_type: Mapped[str | None] = mapped_column(String, nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String, nullable=True)
    owner_org_number: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    geometry = mapped_column(Geometry("POLYGON", srid=4326), nullable=True)
    building_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    living_area_sqm: Mapped[float | None] = mapped_column(Float, nullable=True)
    zoning: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Property(id={self.id}, designation='{self.designation}')>"
