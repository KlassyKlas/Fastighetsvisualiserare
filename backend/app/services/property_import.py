"""Tolkning av fastighetsfiler (CSV/GeoJSON) till ``PropertyCreate`` — utan databas.

Importskriptet ``scripts/import_properties.py`` läser en fil med den här
modulen och skriver resultatet med ``upsert_properties`` (samma väg som
``scripts/seed.py``). Allt här är ren, testbar tolkning:

- rubriker normaliseras och mappas till fält via ``COLUMN_ALIASES``,
- svenska talformat tolkas ("1 234 567 kr", "1.234.567", "12,5"),
- geometrier läses som WKT/GeoJSON eller lng/lat-kolumner och
  transformeras vid behov till WGS84 med pyproj,
- omappade kolumner hamnar i ``metadata_json``.

Geometrierna lämnas som GeoJSON-dictar i WGS84. Skrivningen till PostGIS
sker via ``app/services/geo.py`` inne i ``upsert_properties`` (järnregel 3)
— den här modulen skriver aldrig något själv.
"""

import csv
import io
import json
import math
import re
import unicodedata
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, NamedTuple

from pydantic import ValidationError
from pyproj import Transformer
from pyproj.exceptions import CRSError
from shapely import force_2d, wkt
from shapely.errors import ShapelyError
from shapely.geometry import Point, box, shape
from shapely.geometry import mapping as geojson_mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform
from shapely.validation import explain_validity

from app.domain import PropertyType
from app.schemas import PropertyCreate
from app.services.geo import WGS84_SRID

# Meter per breddgrad — samma approximation som
# scripts/export_sample_data.py::_buffer_wgs84.
M_PER_DEG_LAT = 111_320.0

# Pseudofält som inte finns i PropertyCreate men som styr geometrin.
GEOMETRY_FIELD = "geometry"
LONGITUDE_FIELD = "longitude"
LATITUDE_FIELD = "latitude"

POLYGON_TYPES = ("Polygon", "MultiPolygon")

# Fält i PropertyCreate → accepterade rubriker (jämförs efter
# normalize_header). Fältnamnen själva accepteras alltid.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "designation": ("beteckning", "fastighetsbeteckning", "fastighet"),
    "municipality": ("kommun",),
    "county": ("län", "lan"),
    "area_sqm": ("area", "areal", "tomtarea", "tomtareal", "aream2", "areakvm"),
    "assessed_value_sek": ("taxeringsvärde", "taxeringsvarde", "taxvärde"),
    "property_type": ("typ", "fastighetstyp", "kategori"),
    "owner_name": ("ägare", "agare", "ägarnamn", "lagfarenägare"),
    "owner_org_number": ("orgnr", "organisationsnummer", "ägarorgnr"),
    "address": ("adress", "gatuadress"),
    "postal_code": ("postnummer", "postnr"),
    "city": ("ort", "postort", "stad"),
    "building_year": ("byggår", "byggar", "byggnadsår"),
    "living_area_sqm": ("boarea", "bostadsarea", "boyta"),
    "zoning": ("detaljplan", "plan"),
    GEOMETRY_FIELD: ("geometri", "wkt", "geojson"),
    LONGITUDE_FIELD: ("lng", "lon", "long", "longitud", "x", "öst", "east"),
    LATITUDE_FIELD: ("lat", "latitud", "y", "nord", "north"),
}

_INT_FIELDS = frozenset({"assessed_value_sek", "building_year"})
_DECIMAL_FIELDS = frozenset({"area_sqm", "living_area_sqm"})

# Kandidater i prioritetsordning vid lika antal i rubrikraden: ',' sist,
# eftersom kommatecken kan ingå i en rubrik ("Adress, ort").
CSV_DELIMITERS = ";\t,"
CSV_FALLBACK_DELIMITER = ";"
# csv-modulens standardgräns (128 kB) räcker inte för en detaljerad
# MULTIPOLYGON ur QGIS; det här är i praktiken obegränsat men ryms i en
# C long även på Windows.
CSV_FIELD_SIZE_LIMIT = 2**31 - 1
# Utan BOM provas dessa i tur och ordning; en UTF-16-BOM (Excels
# "Unicode-text") avkodas som UTF-16.
FILE_ENCODINGS = ("utf-8-sig", "cp1252")
UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")
GEOJSON_SUFFIXES = frozenset({".geojson", ".json"})


class ImportFormatError(ValueError):
    """Fel som gäller hela filen (inte en enskild rad): saknad
    beteckningskolumn, motstridiga kolumner, okänt SRID, oläsbar fil."""


class SourceRow(NamedTuple):
    """En rad ur filen med sitt radnummer: den fysiska raden i CSV:n (rubrikraden
    är rad 1) eller feature-numret i en GeoJSON (första feature är 1)."""

    line: int
    values: Mapping[str, object]


@dataclass(frozen=True)
class RowProblem:
    """Ett problem på en rad — raden importeras inte."""

    line: int
    designation: str | None
    message: str


@dataclass
class ImportResult:
    items: list[PropertyCreate] = field(default_factory=list)
    problems: list[RowProblem] = field(default_factory=list)
    # Giltiga rader utan polygon (syns inte på kartan) …
    without_geometry: int = 0
    # … varav rader med bara en punkt, som hade fått en yta med point_buffer_m.
    points_without_buffer: int = 0
    rows_read: int = 0
    # Rubrik → fält enligt första raden, så att skriptet kan visa hur filen tolkades.
    column_mapping: dict[str, str] = field(default_factory=dict)
    extra_columns: list[str] = field(default_factory=list)

    @property
    def failed_lines(self) -> int:
        """Antal rader med minst ett problem."""
        return len({problem.line for problem in self.problems})


# --- Rubriker ----------------------------------------------------------------


def normalize_header(name: object) -> str:
    """Normalisera en kolumnrubrik för aliasuppslag.

    Gemener, trimmat, utan mellanslag, punkter, understreck, bindestreck
    och parentesinnehåll: "Taxeringsvärde (kr)" → "taxeringsvärde",
    "Org.nr" → "orgnr", "owner_name" → "ownername".
    """
    text = unicodedata.normalize("NFC", str(name)).lstrip("\ufeff").strip().lower()
    text = re.sub(r"\(.*?\)", "", text)
    return re.sub(r"[\s._\-]+", "", text)


def _build_header_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for field_name, aliases in COLUMN_ALIASES.items():
        for alias in (field_name, *aliases):
            key = normalize_header(alias)
            if lookup.get(key, field_name) != field_name:
                raise RuntimeError(
                    f"Aliaset {alias!r} pekar på både {lookup[key]} och {field_name}"
                )
            lookup[key] = field_name
    return lookup


_HEADER_LOOKUP = _build_header_lookup()


def map_headers(headers: Iterable[str]) -> dict[str, str]:
    """Originalrubrik → fältnamn för de rubriker som känns igen.

    Raises:
        ImportFormatError: om två kolumner betyder samma fält.
    """
    header_map: dict[str, str] = {}
    by_field: dict[str, str] = {}
    for header in headers:
        field_name = _HEADER_LOOKUP.get(normalize_header(header))
        if field_name is None:
            continue
        if field_name in by_field:
            raise ImportFormatError(
                f"Kolumnerna {by_field[field_name]!r} och {header!r} betyder båda "
                f"{field_name} — ta bort en av dem"
            )
        by_field[field_name] = header
        header_map[header] = field_name
    return header_map


# --- Värden ------------------------------------------------------------------


def _as_text(value: object) -> str | None:
    """Trimmad sträng, eller None för tomt/saknat värde."""
    if value is None:
        return None
    if isinstance(value, dict | list):
        text = json.dumps(value, ensure_ascii=False)
    elif isinstance(value, float) and value.is_integer():
        text = str(int(value))
    else:
        text = str(value).strip()
    return text or None


# Avslutande enhet: börjar med en bokstav (eller ²³%) och får sedan innehålla
# siffror, snedstreck och punkter ("kr", "m²", "m2", "kvm", "kr/år", "st.").
# Ett exponent-e ("1e5", "1,25E+08") är inte en enhet.
_UNIT_SUFFIX = re.compile(r"(?![eE][+-]?\d)[a-zA-ZåäöÅÄÖ²³%][\w²³%/.]*$")
_UNIT_PREFIX = re.compile(r"^[a-zA-ZåäöÅÄÖ]+")
# ",-" och ":-" efter ett belopp ("1 250 000,-")
_ORE_SUFFIX = re.compile(r"[,:]-$")


def _remove_thousands_separator(integer_part: str, separator: str) -> str | None:
    """Ta bort tusentalsavgränsaren: "1.234.567" → "1234567". None om grupperna
    efter den första inte är tresiffriga ("12..5", "1,2,3") eller om något
    annat än siffror ingår."""
    first, *rest = integer_part.split(separator)
    if not first.isdigit() or not all(len(group) == 3 and group.isdigit() for group in rest):
        return None
    return first + "".join(rest)


def _normalize_number(text: str) -> str | None:
    """Svenskt (eller engelskt) talformat → sträng som float() förstår.

    Mellanslag (även hårda) är tusentalsavgränsare; en inledande eller
    avslutande enhet ("kr", "m²", "m2", "kr/år", "SEK", ",-") tas bort.
    Finns både punkt och komma är den sista decimaltecknet; enbart flera
    punkter eller flera kommatecken är tusentalsavgränsare (och måste då
    stå mellan tresiffriga grupper); ett ensamt komma eller en ensam punkt
    är decimaltecken. Returnerar None om inget tal återstår eller om
    tusentalsgrupperna inte stämmer.
    """
    cleaned = re.sub(r"\s", "", text)
    # Prefixet först: suffixmönstret får innehålla siffror och skulle annars
    # äta upp hela "SEK100".
    cleaned = _UNIT_PREFIX.sub("", cleaned)
    cleaned = _ORE_SUFFIX.sub("", cleaned)
    cleaned = _UNIT_SUFFIX.sub("", cleaned)
    sign = ""
    if cleaned[:1] in ("+", "-"):
        sign, cleaned = cleaned[0], cleaned[1:]
    if not cleaned:
        return None
    commas, dots = cleaned.count(","), cleaned.count(".")
    if commas and dots:
        last = max(cleaned.rfind(","), cleaned.rfind("."))
        thousands = "." if cleaned[last] == "," else ","
        integer_part = _remove_thousands_separator(cleaned[:last], thousands)
        return None if integer_part is None else f"{sign}{integer_part}.{cleaned[last + 1 :]}"
    if commas > 1 or dots > 1:
        integer_part = _remove_thousands_separator(cleaned, "," if commas > 1 else ".")
        return None if integer_part is None else sign + integer_part
    return sign + cleaned.replace(",", ".")


def parse_decimal(value: object) -> float | None:
    """Tolka ett decimaltal; tomt → None.

    Raises:
        ValueError: om värdet inte är ett tal.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"'{value}' är inte ett tal")
    if isinstance(value, int | float):
        number = float(value)
    else:
        text = str(value).strip()
        if not text:
            return None
        normalized = _normalize_number(text)
        if normalized is None:
            raise ValueError(f"'{text}' är inte ett tal")
        try:
            number = float(normalized)
        except ValueError:
            raise ValueError(f"'{text}' är inte ett tal") from None
    if not math.isfinite(number):
        raise ValueError(f"'{value}' är inte ett tal")
    return number


def parse_int(value: object) -> int | None:
    """Tolka ett heltal; tomt → None. "12,0" godtas, "12,5" är ett fel.

    Raises:
        ValueError: om värdet inte är ett tal eller har decimaler.
    """
    number = parse_decimal(value)
    if number is None:
        return None
    if not number.is_integer():
        raise ValueError(f"'{str(value).strip()}' är inte ett heltal")
    return int(number)


_PROPERTY_TYPES: dict[str, PropertyType] = {t.value: t for t in PropertyType}


def parse_property_type(value: object) -> PropertyType | None:
    """Skiftlägesokänslig match mot PropertyType-värdena; tomt → None.

    Raises:
        ValueError: vid okänt värde — meddelandet listar giltiga värden.
    """
    text = _as_text(value)
    if text is None:
        return None
    property_type = _PROPERTY_TYPES.get(text.casefold())
    if property_type is None:
        raise ValueError(
            f"okänd fastighetstyp '{text}' — giltiga värden: {', '.join(_PROPERTY_TYPES)}"
        )
    return property_type


# --- Geometri ----------------------------------------------------------------


@lru_cache
def _to_wgs84_transformer(srid: int) -> Transformer:
    return Transformer.from_crs(srid, WGS84_SRID, always_xy=True)


def check_srid(srid: int) -> None:
    """Kontrollera att SRID:t är känt för pyproj.

    Raises:
        ImportFormatError: vid okänt SRID.
    """
    if srid == WGS84_SRID:
        return
    try:
        _to_wgs84_transformer(srid)
    except CRSError as exc:
        raise ImportFormatError(
            f"Okänt SRID {srid} (SWEREF99 TM är 3006, WGS84 är 4326): {exc}"
        ) from exc


def to_wgs84(geom: BaseGeometry, srid: int) -> BaseGeometry:
    """Transformera en geometri från `srid` till WGS84 (ingen åtgärd för 4326)."""
    if srid == WGS84_SRID:
        return geom
    return shapely_transform(_to_wgs84_transformer(srid).transform, geom)


def _check_wgs84_bounds(geom: BaseGeometry) -> None:
    minx, miny, maxx, maxy = geom.bounds
    if not (-180 <= minx <= maxx <= 180 and -90 <= miny <= maxy <= 90):
        raise ValueError(
            f"koordinater utanför WGS84 ({minx:.10g}, {miny:.10g}) — ange --srid om filen "
            "är i ett annat koordinatsystem (t.ex. 3006 för SWEREF99 TM)"
        )


# GEOS-formuleringar (shapely.validation.explain_validity) → svenska.
_INVALIDITY_REASONS = {
    "Self-intersection": "geometrin skär sig själv",
    "Ring Self-intersection": "ringen skär sig själv",
    "Hole lies outside shell": "ett hål ligger utanför ytterringen",
    "Nested holes": "ett hål ligger inuti ett annat hål",
    "Interior is disconnected": "ytan hänger inte ihop",
    "Nested shells": "en yta ligger inuti en annan",
    "Duplicate Rings": "två ringar är identiska",
    "Too few points in geometry component": "för få punkter",
    "Invalid Coordinate": "ogiltig koordinat",
    "Ring is not closed": "ringen är inte sluten",
}


def _describe_invalidity(geom: BaseGeometry) -> str:
    """Varför geometrin är ogiltig, på svenska och med platsen i WGS84."""
    reason = explain_validity(geom)
    match = re.fullmatch(r"(.*?)\s*\[(\S+) (\S+)\]", reason)
    if match is None:
        return reason
    text = _INVALIDITY_REASONS.get(match.group(1), match.group(1))
    return f"{text} vid ({match.group(2)}, {match.group(3)})"


# GEOS/shapely-formuleringar vid tolkningen → svenska (sökmönster, ersättning).
_PARSE_ERROR_TRANSLATIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"do not form a closed linestring"),
        "ringen är inte sluten — sista punkten måste vara samma som den första",
    ),
    (
        re.compile(r"Invalid number of points in LinearRing|requires at least 4 coordinates"),
        "för få punkter i ringen — minst fyra, där den sista upprepar den första",
    ),
    (
        re.compile(r"Unknown (?:geometry )?type: '(.+?)'"),
        r"okänd geometrityp '\1' — förväntade WKT (POLYGON …) eller GeoJSON",
    ),
    (
        re.compile(r"Expected number but encountered word: '(.+?)'"),
        r"väntade ett tal men fann '\1'",
    ),
    (re.compile(r"Expected \w+ but encountered end of stream"), "WKT-strängen slutar för tidigt"),
    (re.compile(r"Unexpected text after end of geometry"), "text efter geometrins slut"),
)
_EWKT_PREFIX = re.compile(r"^SRID=(\d+);", re.IGNORECASE)


def _describe_parse_error(exc: Exception) -> str:
    """Svensk text för ett tolkningsfel; okända fel behåller bibliotekets detalj."""
    if isinstance(exc, KeyError) and exc.args:
        return f"GeoJSON-geometrin saknar {exc.args[0]!r}"
    # "IllegalArgumentException: …" / "ParseException: …" → bara texten
    detail = re.sub(r"^\w+(?:Exception|Error): ", "", str(exc))
    for pattern, swedish in _PARSE_ERROR_TRANSLATIONS:
        match = pattern.search(detail)
        if match is not None:
            return match.expand(swedish)
    return f"kunde inte tolka värdet som WKT eller GeoJSON ({detail})"


def _split_ewkt(text: str, default_srid: int) -> tuple[str, int]:
    """Skala av ett EWKT-prefix ("SRID=3006;POLYGON(...)", som PostGIS
    ST_AsEWKT ger). Prefixets SRID gäller för värdet i stället för filens.

    Raises:
        ValueError: om prefixets SRID är okänt för pyproj.
    """
    match = _EWKT_PREFIX.match(text)
    if match is None:
        return text, default_srid
    srid = int(match.group(1))
    if srid != WGS84_SRID:
        try:
            _to_wgs84_transformer(srid)
        except CRSError as exc:
            raise ValueError(f"okänt SRID {srid} i EWKT-prefixet") from exc
    return text[match.end() :], srid


def parse_geometry(value: object, *, srid: int = WGS84_SRID) -> BaseGeometry | None:
    """WKT/EWKT eller GeoJSON (sträng eller dict) → shapely-geometri i WGS84.

    Tomt värde → None. Z-koordinater tas bort (kolumnerna är 2D). Ett
    EWKT-prefix ("SRID=3006;…") anger värdets eget SRID och vinner över
    `srid`.

    Raises:
        ValueError: om värdet inte går att tolka, ligger utanför WGS84
            eller är topologiskt ogiltigt (t.ex. självskärande).
    """
    if value is None:
        return None
    try:
        if isinstance(value, Mapping):
            geom = shape(value)
        else:
            text = str(value).strip()
            if not text:
                return None
            if text.startswith("{"):
                geom = shape(json.loads(text))
            else:
                text, srid = _split_ewkt(text, srid)
                geom = wkt.loads(text)
    except (ShapelyError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"ogiltig geometri: {_describe_parse_error(exc)}") from exc
    if geom.is_empty:
        return None
    geom = to_wgs84(force_2d(geom), srid)
    _check_wgs84_bounds(geom)
    if not geom.is_valid:
        # PostGIS tar emot ogiltiga polygoner, men ST_Intersects/ST_DWithin
        # kan sedan fela på dem — för alla anrop, inte bara den här raden.
        raise ValueError(f"ogiltig polygon: {_describe_invalidity(geom)} — rätta den i t.ex. QGIS")
    return geom


def square_around_point(lng: float, lat: float, half_size_m: float) -> BaseGeometry:
    """Axelparallell kvadrat ±half_size_m kring en WGS84-punkt.

    Meter → grader med samma ekvirektangulära approximation som
    ``scripts/export_sample_data.py::_buffer_wgs84``: en breddgrad är
    M_PER_DEG_LAT meter och en längdgrad krymper med cos(lat). Felet är
    på promillenivå i Sverige — mer än nog för en symbolisk tomtyta.
    """
    d_lat = half_size_m / M_PER_DEG_LAT
    d_lng = half_size_m / (M_PER_DEG_LAT * math.cos(math.radians(lat)))
    return box(lng - d_lng, lat - d_lat, lng + d_lng, lat + d_lat)


def _parse_point(lng_raw: object, lat_raw: object, *, srid: int) -> Point | None:
    lng = parse_decimal(lng_raw)
    lat = parse_decimal(lat_raw)
    if lng is None and lat is None:
        return None
    if lng is None or lat is None:
        raise ValueError("både longitud och latitud krävs")
    point = to_wgs84(Point(lng, lat), srid)
    _check_wgs84_bounds(point)
    return point


# --- Rader -------------------------------------------------------------------


@dataclass(frozen=True)
class _Options:
    srid: int
    point_buffer_m: float | None
    extra_to_metadata: bool


class _FieldError(ValueError):
    """Ett fel knutet till ett fält — raden rapporterar det under fältets rubrik."""

    def __init__(self, field_name: str, message: str) -> None:
        super().__init__(message)
        self.field_name = field_name


@dataclass
class _ParsedRow:
    item: PropertyCreate | None
    problems: list[str]
    designation: str | None
    point_without_buffer: bool = False


def _is_ignored_header(header: object) -> bool:
    """None (csv: fler värden än rubriker) eller tom rubrik (avslutande ';' i rubrikraden)."""
    return header is None or not str(header).strip()


# Pydantic-feltyp → (ctx-nyckel, svensk mall). Övriga fel får Pydantics egen text.
_LIMIT_MESSAGES = {
    "greater_than_equal": ("ge", "måste vara minst {}"),
    "less_than_equal": ("le", "får vara högst {}"),
    "greater_than": ("gt", "måste vara större än {}"),
    "less_than": ("lt", "måste vara mindre än {}"),
}


def _format_limit(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _describe_validation_error(error: Mapping[str, Any]) -> str:
    """Svensk text för de Pydantic-fel som kan uppstå på en rad (gränsvärden, tom sträng)."""
    if error["type"] == "string_too_short":
        return "får inte vara tomt"
    limit = _LIMIT_MESSAGES.get(error["type"])
    ctx = error.get("ctx") or {}
    if limit is not None and limit[0] in ctx:
        return limit[1].format(_format_limit(ctx[limit[0]]))
    return error["msg"]


def _parse_field(field_name: str, raw: object) -> Any:
    if field_name in _INT_FIELDS:
        return parse_int(raw)
    if field_name in _DECIMAL_FIELDS:
        return parse_decimal(raw)
    if field_name == "property_type":
        return parse_property_type(raw)
    return _as_text(raw)


def _resolve_geometry(
    geometry_raw: object, lng_raw: object, lat_raw: object, options: _Options
) -> tuple[dict[str, Any] | None, bool]:
    """GeoJSON-dict i WGS84 (eller None) samt om en punkt föll bort utan buffert.

    Geometrikolumnen vinner över lng/lat. En punkt (från GeoJSON eller
    lng/lat) blir en kvadrat om point_buffer_m är satt, annars None.

    Raises:
        _FieldError: ogiltig geometri, ofullständiga koordinater eller fel geometrityp.
    """
    try:
        geom = parse_geometry(geometry_raw, srid=options.srid)
    except ValueError as exc:
        raise _FieldError(GEOMETRY_FIELD, str(exc)) from exc
    if geom is None:
        try:
            geom = _parse_point(lng_raw, lat_raw, srid=options.srid)
        except ValueError as exc:
            raise _FieldError(LONGITUDE_FIELD, str(exc)) from exc
    if geom is None:
        return None, False

    if isinstance(geom, Point):
        if options.point_buffer_m is None:
            return None, True
        geom = square_around_point(geom.x, geom.y, options.point_buffer_m)
    elif geom.geom_type not in POLYGON_TYPES:
        raise _FieldError(
            GEOMETRY_FIELD,
            f"geometrin måste vara POLYGON eller MULTIPOLYGON (eller en punkt), "
            f"inte {geom.geom_type}",
        )
    return json.loads(json.dumps(geojson_mapping(geom))), False


def _parse_row(
    row: Mapping[str, object], header_map: dict[str, str], options: _Options
) -> _ParsedRow:
    values: dict[str, Any] = {}
    extras: dict[str, str] = {}
    problems: list[str] = []
    headers_by_field: dict[str, str] = {}
    geometry_raw: object = None
    lng_raw: object = None
    lat_raw: object = None

    for header, raw in row.items():
        if _is_ignored_header(header):
            continue
        field_name = header_map.get(header)
        if field_name is None:
            text = _as_text(raw)
            if options.extra_to_metadata and text is not None:
                extras[header] = text
            continue
        headers_by_field[field_name] = header
        if field_name == GEOMETRY_FIELD:
            geometry_raw = raw
        elif field_name == LONGITUDE_FIELD:
            lng_raw = raw
        elif field_name == LATITUDE_FIELD:
            lat_raw = raw
        else:
            try:
                values[field_name] = _parse_field(field_name, raw)
            except ValueError as exc:
                problems.append(f"{header}: {exc}")

    designation = values.get("designation")
    if designation is None:
        problems.append("saknar fastighetsbeteckning")

    geometry: dict[str, Any] | None = None
    point_without_buffer = False
    try:
        geometry, point_without_buffer = _resolve_geometry(geometry_raw, lng_raw, lat_raw, options)
    except _FieldError as exc:
        problems.append(f"{headers_by_field.get(exc.field_name, exc.field_name)}: {exc}")

    if problems:
        return _ParsedRow(None, problems, designation)

    values["geometry"] = geometry
    values["metadata_json"] = extras
    try:
        item = PropertyCreate(**values)
    except ValidationError as exc:
        for error in exc.errors():
            field_name = ".".join(str(part) for part in error["loc"])
            header = headers_by_field.get(field_name, field_name)
            problems.append(f"{header}: {_describe_validation_error(error)}")
        return _ParsedRow(None, problems, designation)
    return _ParsedRow(item, [], designation, point_without_buffer)


def _is_blank(row: Mapping[str, object]) -> bool:
    return all(_as_text(value) is None for value in row.values())


def _numbered(
    rows: Iterable[SourceRow | Mapping[str, object]], first_line: int
) -> Iterator[SourceRow]:
    """Rader från läsarna bär sitt radnummer; rena mappningar numreras från first_line."""
    for line, row in enumerate(rows, start=first_line):
        yield row if isinstance(row, SourceRow) else SourceRow(line, row)


def parse_rows(
    rows: Iterable[SourceRow | Mapping[str, object]],
    *,
    srid: int = WGS84_SRID,
    point_buffer_m: float | None = None,
    extra_to_metadata: bool = True,
    first_line: int = 2,
) -> ImportResult:
    """Tolka rader (rubrik → värde) till PropertyCreate-objekt.

    Rader från ``read_file``/``read_csv``/``read_geojson`` är ``SourceRow``
    och rapporteras med sitt radnummer i filen (feature-nummer för
    GeoJSON). Rena mappningar numreras löpande från `first_line` (2 = första
    dataraden i en CSV med rubrikrad). Helt tomma rader hoppas över. Ett
    Pydantic-valideringsfel blir ett RowProblem med kolumnrubriken, aldrig
    ett undantag. Dubbletter av beteckningen: första raden vinner, senare
    rapporteras som problem. Rader som saknar beteckning blir radproblem;
    saknas beteckningen i alla rader är det kolumnen som saknas — ett
    filfel.

    Raises:
        ImportFormatError: okänt SRID, ogiltig buffert, saknad
            beteckningskolumn eller motstridiga kolumner.
    """
    check_srid(srid)
    if point_buffer_m is not None and point_buffer_m <= 0:
        raise ImportFormatError("point_buffer_m måste vara större än 0")
    options = _Options(srid, point_buffer_m, extra_to_metadata)

    result = ImportResult()
    first_line_of: dict[str, int] = {}
    # Nyckeluppsättning → rubrikmappning. CSV-rader har alla samma nycklar;
    # GeoJSON-features kan sakna enstaka attribut och får då egna mappningar.
    header_maps: dict[tuple[str, ...], dict[str, str]] = {}
    first_headers: tuple[str, ...] = ()

    for line, row in _numbered(rows, first_line):
        if _is_blank(row):
            continue
        result.rows_read += 1

        headers = tuple(header for header in row if not _is_ignored_header(header))
        header_map = header_maps.get(headers)
        if header_map is None:
            header_map = map_headers(headers)
            if not header_maps:
                first_headers = headers
                result.column_mapping = dict(header_map)
                result.extra_columns = [h for h in headers if h not in header_map]
            header_maps[headers] = header_map

        parsed = _parse_row(row, header_map, options)
        if parsed.item is None:
            result.problems.extend(
                RowProblem(line, parsed.designation, message) for message in parsed.problems
            )
            continue

        designation = parsed.item.designation
        if designation in first_line_of:
            result.problems.append(
                RowProblem(
                    line,
                    designation,
                    f"dubblett av beteckningen '{designation}' — första förekomsten "
                    f"(rad {first_line_of[designation]}) används",
                )
            )
            continue
        first_line_of[designation] = line
        result.items.append(parsed.item)
        if parsed.item.geometry is None:
            result.without_geometry += 1
        if parsed.point_without_buffer:
            result.points_without_buffer += 1

    # Saknas beteckningen i alla rader är det kolumnen som saknas (filfel);
    # saknas den bara i några rader är de redan rapporterade som radproblem.
    if result.rows_read and not any("designation" in m.values() for m in header_maps.values()):
        raise ImportFormatError(
            "Ingen kolumn för fastighetsbeteckning hittades (t.ex. Beteckning eller "
            f"Fastighetsbeteckning). Kolumner i filen: {', '.join(first_headers) or '(inga)'}"
        )
    return result


# --- Läsare ------------------------------------------------------------------


def _decode(raw: bytes, path: Path) -> str:
    """Bytes → text: UTF-16 vid BOM (Excels "Unicode-text"), annars UTF-8
    (med eller utan BOM) med cp1252 som reserv (Excels vanliga CSV på
    svenska Windows).

    Raises:
        ImportFormatError: om ingen kodning passar.
    """
    encodings = ("utf-16",) if raw.startswith(UTF16_BOMS) else FILE_ENCODINGS
    for encoding in encodings:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportFormatError(f"{path}: kunde inte avkoda filen — spara den som UTF-8")


def _sniff_delimiter(text: str) -> str:
    """Avgränsaren avgörs av rubrikraden: den av `;`, tab och `,` som
    förekommer flest gånger där (vid lika antal i den ordningen — rubriker
    innehåller sällan `;` eller tab, men gärna kommatecken som i "Adress,
    ort"). Saknar rubrikraden alla tre får csv.Sniffer gissa på de första
    raderna, och som sista reserv gäller `;`."""
    header = next((line for line in text.splitlines() if line.strip()), "")
    # Avgränsare inne i citerade rubriker ('"Adress, ort"') räknas inte.
    unquoted = re.sub(r'"[^"]*"', '""', header)
    best = max(CSV_DELIMITERS, key=unquoted.count)
    if unquoted.count(best):
        return best
    sample = "\n".join(text.splitlines()[:20])
    try:
        return csv.Sniffer().sniff(sample, delimiters=CSV_DELIMITERS).delimiter
    except csv.Error:
        return CSV_FALLBACK_DELIMITER


def _check_duplicate_headers(fieldnames: Sequence[str], path: Path) -> None:
    """Dubblerade rubriker skulle tyst skriva över varandra (DictReader: sista vinner).

    Raises:
        ImportFormatError: om en (trimmad) rubrik förekommer mer än en gång.
    """
    names = [name for name in fieldnames if name]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        listed = ", ".join(repr(name) for name in duplicates)
        raise ImportFormatError(
            f"{path}: dubblerade rubriker ({listed}) — ge kolumnerna olika namn"
        )


def read_csv(path: Path | str) -> list[SourceRow]:
    """Läs en CSV med rubrikrad.

    Kodning enligt ``_decode`` (UTF-8, UTF-16 med BOM eller cp1252);
    avgränsare `;`, `,` eller tab enligt ``_sniff_delimiter``. Rubriker
    trimmas; tomma rubriker (avslutande `;` i rubrikraden) följer med i
    raderna men ignoreras av ``parse_rows``. Radnumret är radens första
    fysiska rad i filen (rubrikraden är rad 1) — helt tomma rader och
    citerade radbrytningar rubbar inte numreringen.

    Raises:
        ImportFormatError: tom fil, dubblerade rubriker, oläsbar kodning
            eller en rad csv-modulen inte kan tolka.
        OSError: om filen inte kan läsas.
    """
    path = Path(path)
    text = _decode(path.read_bytes(), path)
    csv.field_size_limit(CSV_FIELD_SIZE_LIMIT)
    # newline="" så att csv-modulen själv hanterar radbrytningarna (även
    # inne i citerade fält) och line_num räknar fysiska rader.
    reader = csv.DictReader(
        io.StringIO(text, newline=""), delimiter=_sniff_delimiter(text), skipinitialspace=True
    )
    if not reader.fieldnames:
        raise ImportFormatError(f"{path}: filen är tom")
    reader.fieldnames = [name.strip() for name in reader.fieldnames]
    _check_duplicate_headers(reader.fieldnames, path)
    rows: list[SourceRow] = []
    try:
        for row in reader:
            beyond = row.pop(None, None) or []  # värden bortom sista rubriken
            # line_num är radens sista fysiska rad: citerade radbrytningar
            # räknas bort så att numret pekar på radens första rad.
            embedded_newlines = sum(str(v).count("\n") for v in (*row.values(), *beyond) if v)
            values = {header: value if value is not None else "" for header, value in row.items()}
            rows.append(SourceRow(reader.line_num - embedded_newlines, values))
    except csv.Error as exc:
        raise ImportFormatError(f"{path}: kunde inte läsa rad {reader.line_num}: {exc}") from exc
    return rows


def read_geojson(path: Path | str) -> list[SourceRow]:
    """Läs en GeoJSON FeatureCollection.

    Varje feature blir en rad (radnummer = feature-nummer från 1) med sina
    properties plus geometri-dicten under nyckeln "geometry".

    Raises:
        ImportFormatError: oläsbar kodning, ogiltig JSON eller inte en
            FeatureCollection.
        OSError: om filen inte kan läsas.
    """
    path = Path(path)
    try:
        data = json.loads(_decode(path.read_bytes(), path))
    except json.JSONDecodeError as exc:
        raise ImportFormatError(f"{path}: ogiltig JSON ({exc})") from exc

    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
        features = data.get("features") or []
    elif isinstance(data, dict) and data.get("type") == "Feature":
        features = [data]
    else:
        raise ImportFormatError(f"{path}: förväntade en GeoJSON FeatureCollection")

    rows: list[SourceRow] = []
    for index, feature in enumerate(features, start=1):
        if not isinstance(feature, dict):
            raise ImportFormatError(f"{path}: feature {index} är inte ett objekt")
        properties = feature.get("properties") or {}
        row: dict[str, Any] = {
            str(key): value
            for key, value in properties.items()
            # Feature-geometrin vinner över en ev. geometrikolumn bland attributen.
            if _HEADER_LOOKUP.get(normalize_header(key)) != GEOMETRY_FIELD
        }
        row[GEOMETRY_FIELD] = feature.get("geometry")
        rows.append(SourceRow(index, row))
    return rows


def is_geojson_path(path: Path | str) -> bool:
    """Sant för .geojson/.json — då läses filen som GeoJSON, annars som CSV."""
    return Path(path).suffix.lower() in GEOJSON_SUFFIXES


def read_file(path: Path | str) -> list[SourceRow]:
    """Välj läsare på filändelse: .geojson/.json → GeoJSON, annars CSV."""
    return read_geojson(path) if is_geojson_path(path) else read_csv(path)
