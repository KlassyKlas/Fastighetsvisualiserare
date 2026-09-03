"""Geometrihjälpare: konvertering mellan GeoJSON, shapely och PostGIS-element.

All skrivning till databasen går via ``geojson_to_element`` som alltid
sätter SRID 4326 — PostGIS avvisar annars geometrier mot kolumner med
deklarerad SRID.
"""

import json
from typing import Any

from fastapi import HTTPException
from geoalchemy2 import WKBElement
from geoalchemy2.shape import from_shape
from shapely import force_2d
from shapely.errors import ShapelyError
from shapely.geometry import MultiPolygon, Polygon, shape
from sqlalchemy import ColumnElement, func

WGS84_SRID = 4326


def geojson_to_element(
    geojson: dict[str, Any],
    *,
    allowed_types: tuple[str, ...] | None = None,
) -> WKBElement:
    """Konvertera en GeoJSON-geometri till ett PostGIS-element med SRID 4326.

    Polygoner promoveras till MultiPolygon så att de passar
    Property-kolumnens deklarerade typ. Z-koordinater tas bort —
    kolumnernas typmod är 2D och PostGIS avvisar annars hela skrivningen
    (Trafikverket levererar ibland "POINT Z (...)"). Koordinaterna måste
    ligga i WGS84:s intervall: PostGIS tar emot vad som helst som
    geometry, men geography-casten — och därmed den genererade
    påverkanszonen — avvisar t.ex. SWEREF 99 TM-koordinater, och det ska
    ge ett begripligt fel här i stället för ett databasfel per rad.

    Args:
        allowed_types: om satt måste geometritypen (efter promovering)
            vara en av dessa — annars ValueError. Används av
            fastighetsflödena för att ge 422 i stället för databasfel.

    Raises:
        ValueError: om geometrin inte är giltig GeoJSON eller har fel typ.
    """
    try:
        geom = force_2d(shape(geojson))
    except (ShapelyError, AttributeError, KeyError, TypeError) as exc:
        raise ValueError(f"Ogiltig GeoJSON-geometri: {exc}") from exc

    if isinstance(geom, Polygon):
        geom = MultiPolygon([geom])

    if not geom.is_empty:
        min_x, min_y, max_x, max_y = geom.bounds
        if not (-180 <= min_x <= max_x <= 180 and -90 <= min_y <= max_y <= 90):
            raise ValueError(
                "Koordinater utanför WGS84 (longitud ±180, latitud ±90) — "
                "geometrin ser ut att vara projicerad (t.ex. SWEREF 99 TM)"
            )

    if allowed_types is not None and geom.geom_type not in allowed_types:
        raise ValueError(
            f"Geometritypen {geom.geom_type} stöds inte här — förväntade {', '.join(allowed_types)}"
        )

    return from_shape(geom, srid=WGS84_SRID)


def intersects_bbox(column: Any, bbox: tuple[float, float, float, float]) -> ColumnElement[bool]:
    """Filtervillkor: geometrin i ``column`` skär rutan väst,syd,öst,norr (WGS84).

    ST_Intersects (inte ST_Within): geometrier som korsar rutans kant ska
    också med i svaret. Används av alla bbox-filter i tjänstelagret.
    """
    west, south, east, north = bbox
    return func.ST_Intersects(column, func.ST_MakeEnvelope(west, south, east, north, WGS84_SRID))


def parse_geojson_column(value: str | None) -> dict[str, Any] | None:
    """Tolka resultatet av ST_AsGeoJSON (en JSON-sträng eller NULL)."""
    if value is None:
        return None
    return json.loads(value)


def parse_bbox(bbox: str) -> tuple[float, float, float, float]:
    """Tolka en bbox-frågeparameter "väst,syd,öst,norr" i WGS84.

    Raises:
        HTTPException: 400 om formatet är ogiltigt.
    """
    try:
        west, south, east, north = (float(part) for part in bbox.split(","))
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Ogiltigt bbox-format. Använd: väst,syd,öst,norr (WGS84)",
        ) from exc

    longitudes_ok = -180 <= west <= 180 and -180 <= east <= 180
    latitudes_ok = -90 <= south <= 90 and -90 <= north <= 90
    if not (longitudes_ok and latitudes_ok):
        raise HTTPException(
            status_code=400,
            detail="bbox-koordinater utanför giltigt intervall för WGS84",
        )

    return west, south, east, north
