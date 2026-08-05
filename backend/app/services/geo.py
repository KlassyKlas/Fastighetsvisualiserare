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
from shapely.errors import ShapelyError
from shapely.geometry import MultiPolygon, Polygon, shape

WGS84_SRID = 4326


def geojson_to_element(geojson: dict[str, Any]) -> WKBElement:
    """Konvertera en GeoJSON-geometri till ett PostGIS-element med SRID 4326.

    Polygoner promoveras till MultiPolygon så att de passar
    Property-kolumnens deklarerade typ.

    Raises:
        ValueError: om geometrin inte är giltig GeoJSON.
    """
    try:
        geom = shape(geojson)
    except (ShapelyError, AttributeError, KeyError, TypeError) as exc:
        raise ValueError(f"Ogiltig GeoJSON-geometri: {exc}") from exc

    if isinstance(geom, Polygon):
        geom = MultiPolygon([geom])

    return from_shape(geom, srid=WGS84_SRID)


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
