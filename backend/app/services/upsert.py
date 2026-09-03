"""Gemensam upsert för synkflödena (projekt, fastigheter, detaljplaner, DeSO).

Alla fyra tabeller skrivs på samma sätt: en INSERT ... ON CONFLICT DO
UPDATE per rad med konflikt på källans nyckel — inga N+1-läsfrågor — i
en savepoint per rad, så att ett enskilt trasigt objekt räknas som
skipped i stället för att fälla hela synkroniseringen. Oförändrade rader
rörs inte alls (WHERE-klausul på uppdateringen): updated_at får bara
flyttas fram när radens innehåll faktiskt ändrats. Utan det tänder varje
omsynkning falska "ändrat"-notiser i bevakade områden (händelsefrågan
jämför updated_at mot last_seen_at) och synkresultatets upserted-räkning
blir meningslös.

Kostnadsnot: infrastructure_projects.impact_zone är en genererad kolumn,
och PostgreSQL beräknar den för varje föreslagen rad i INSERT ... ON
CONFLICT — även rader som WHERE-klausulen sedan lämnar orörda — och en
gång till för rader som faktiskt uppdateras. Buffringen (~1,4 s för
samtliga korridorer i nationell plan) betalas alltså per synk i stället
för per kartanrop. En UPDATE-först-variant skulle göra oförändrade rader
gratis men kräver två satsformer och geometrin som parameter två gånger;
inte värt det så länge synk är sällsynt och läsning vanlig.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy import ColumnElement, func, or_
from sqlalchemy.dialects.postgresql import Insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.geo import geojson_to_element

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SyncCounts:
    """Utfallet av en upsert: skapade eller faktiskt ändrade, orörda och
    överhoppade rader. Adderas per tabell till synkkörningens totaler."""

    upserted: int = 0
    unchanged: int = 0
    skipped: int = 0

    def __add__(self, other: "SyncCounts") -> "SyncCounts":
        return SyncCounts(
            self.upserted + other.upserted,
            self.unchanged + other.unchanged,
            self.skipped + other.skipped,
        )

    def __str__(self) -> str:
        """Rapportrad för skripten: "3 inskrivna, 2 oförändrade, 0 överhoppade"."""
        return (
            f"{self.upserted} inskrivna, {self.unchanged} oförändrade, {self.skipped} överhoppade"
        )


async def upsert_rows(
    session: AsyncSession,
    model: type,
    items: Iterable[BaseModel],
    *,
    conflict_key: str,
    label: str,
    allowed_geometry_types: tuple[str, ...] | None = None,
) -> SyncCounts:
    """Skriv in rader från en datakälla i ``model`` (se modulens docstring).

    items är ingest-modeller vars fält mappar rakt på modellens kolumner,
    med geometrin som GeoJSON-dict i fältet ``geometry``.

    Args:
        conflict_key: kolumnen som identifierar objektet hos källan
            (external_id, designation, deso_code) — den som konflikten
            löses på och som loggas när en rad hoppas över.
        label: objektslaget i loggraderna ("projekt", "fastighet", ...).
        allowed_geometry_types: tillåtna geometrityper efter promovering
            (yt-tabellerna kräver MultiPolygon); None = alla typer.
    """
    upserted = 0
    unchanged = 0
    skipped = 0

    for item in items:
        values = item.model_dump()
        key = values[conflict_key]
        if values["geometry"] is not None:
            try:
                values["geometry"] = geojson_to_element(
                    values["geometry"], allowed_types=allowed_geometry_types
                )
            except ValueError:
                logger.warning("Hoppar över %s %s: ogiltig geometri", label, key)
                skipped += 1
                continue

        stmt = pg_insert(model).values(**values)
        update_columns = {
            column: getattr(stmt.excluded, column) for column in values if column != conflict_key
        }
        update_columns["updated_at"] = func.now()
        # Skriv aldrig över en befintlig geometri med NULL — källor kan
        # tillfälligt utelämna geometrin för ett objekt de tidigare
        # levererat med geometri (Trafikverket gör det).
        update_columns["geometry"] = func.coalesce(stmt.excluded.geometry, model.geometry)
        stmt = stmt.on_conflict_do_update(
            index_elements=[getattr(model, conflict_key)],
            set_=update_columns,
            where=changed_where(stmt, model, values, conflict_key=conflict_key),
        )
        try:
            async with session.begin_nested():
                result = await session.execute(stmt)
        except SQLAlchemyError:
            logger.warning("Hoppar över %s %s: databasfel vid upsert", label, key, exc_info=True)
            skipped += 1
            continue
        # rowcount 0 = konflikt utan innehållsändring (WHERE föll) — raden
        # är oförändrad och updated_at har inte rörts.
        if result.rowcount:
            upserted += 1
        else:
            unchanged += 1

    return SyncCounts(upserted=upserted, unchanged=unchanged, skipped=skipped)


def changed_where(
    stmt: Insert,
    model: type,
    values: dict[str, Any],
    *,
    conflict_key: str,
) -> ColumnElement[bool]:
    """WHERE-klausul till on_conflict_do_update: sann bara om någon
    datakolumn skiljer sig från den inkommande raden.

    Geometrin jämförs efter samma coalesce-regel som skrivningen
    (inkommande NULL skriver aldrig över befintlig geometri). PostGIS
    ``=`` är exakt koordinatlikhet sedan 2.4, så IS DISTINCT FROM
    fungerar även för geometrikolumner.
    """
    conditions: list[ColumnElement[bool]] = []
    for key in values:
        if key == conflict_key:
            continue
        column = getattr(model, key)
        excluded = getattr(stmt.excluded, key)
        if key == "geometry":
            conditions.append(func.coalesce(excluded, column).is_distinct_from(column))
        else:
            conditions.append(column.is_distinct_from(excluded))
    return or_(*conditions)
