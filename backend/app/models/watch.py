from datetime import datetime

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WatchedArea(Base):
    """Ett användarritat område som bevakas på nya/ändrade objekt.

    Händelsefrågan använder ST_Intersects (ren geometrioperation, inga
    meterberäkningar) — därför räcker det vanliga GiST-indexet och inget
    geography-index behövs.
    """

    __tablename__ = "watched_areas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    # Området ritas som polygon i kartan — en bevakning utan geometri
    # vore meningslös, därför NOT NULL till skillnad från datalagren.
    geometry: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326), nullable=False
    )
    # Sätts till nu vid skapande (en ny bevakning börjar "ren") och
    # flyttas fram när användaren markerar händelserna som sedda.
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<WatchedArea(id={self.id}, name='{self.name}')>"
