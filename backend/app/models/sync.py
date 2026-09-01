from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SyncRun(Base):
    """En körning av POST /infrastructure/sync/{källa} — synkloggen.

    Loggen svarar på "när synkades senast och vad hände?": panelen "Nytt
    sedan senast" använder senaste körningens started_at som tidsankare
    och lagerpanelen visar utfallet per källa. Raden skapas INNAN
    hämtningen börjar (därför server_default på räkningarna) så att även
    en körning som dör i HTTP-lagret lämnar spår. finished_at är NULL
    tills körningen är klar; error sätts bara när den misslyckats.
    """

    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    upserted: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    unchanged: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    skipped: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    truncated: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Felmeddelande (klippt till 500 tecken) när hämtningen misslyckades.
    error: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<SyncRun(id={self.id}, source='{self.source}')>"
