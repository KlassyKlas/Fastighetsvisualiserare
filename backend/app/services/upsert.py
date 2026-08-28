"""Gemensam ändringsdetektering för synk-upserterna.

updated_at får bara flyttas fram när radens innehåll faktiskt ändrats.
Utan detta tänder varje omsynkning falska "ändrat"-notiser i bevakade
områden (händelsefrågan jämför updated_at mot last_seen_at), och
synkresultatets upserted-räkning blir meningslös.
"""

from typing import Any

from sqlalchemy import ColumnElement, func, or_
from sqlalchemy.dialects.postgresql import Insert


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
