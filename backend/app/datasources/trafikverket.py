"""Datakälla: Trafikverkets öppna trafikinformations-API.

Hämtar objekttypen ``Situation`` (trafikstörningar, vägarbeten m.m.).
Observera att detta är läget-just-nu-data — Trafikverkets långsiktiga
investeringsplaner (nationell plan, länsplaner) ligger inte i detta API
och är en framtida, separat datakälla.

Status härleds ur störningens start- och sluttid i stället för att
hårdkodas: framtida starttid → planerad, passerad sluttid → avslutad,
annars pågående.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from xml.sax.saxutils import escape

import httpx
import shapely
from shapely.errors import ShapelyError
from shapely.geometry import mapping

from app.config import get_settings
from app.datasources.base import (
    Bbox,
    DataSource,
    DataSourceError,
    InfrastructureProjectIngest,
    register,
)
from app.domain import ProjectStatus, ProjectType

logger = logging.getLogger(__name__)

API_URL = "https://api.trafikinfo.trafikverket.se/v2/data.json"
SCHEMA_VERSION = "1.5"
REQUEST_LIMIT = 500
DEFAULT_IMPACT_RADIUS_M = 1000.0

# Trafikverkets MessageType → våra projekttyper
MESSAGE_TYPE_MAP: dict[str, ProjectType] = {
    "Vägarbete": ProjectType.VAG,
    "Trafikmeddelande": ProjectType.VAG,
    "Olycka": ProjectType.VAG,
    "Hinder": ProjectType.VAG,
    "Järnväg": ProjectType.JARNVAG,
    "Kollektivtrafik": ProjectType.KOLLEKTIVTRAFIK,
    "Bro": ProjectType.BRO,
    "Tunnel": ProjectType.TUNNEL,
    "Cykelväg": ProjectType.CYKELVAG,
}


def build_request_xml(api_key: str, bbox: Bbox | None = None) -> str:
    """Bygg API-frågan. Med bbox filtreras spatialt redan på serversidan."""
    spatial_filter = ""
    if bbox is not None:
        west, south, east, north = bbox
        spatial_filter = (
            f'<WITHIN name="Deviation.Geometry.WGS84" shape="box" '
            f'value="{west} {south}, {east} {north}" />'
        )

    return f"""<REQUEST>
    <LOGIN authenticationkey="{escape(api_key, {'"': "&quot;"})}" />
    <QUERY objecttype="Situation" schemaversion="{SCHEMA_VERSION}" limit="{REQUEST_LIMIT}">
        <FILTER>{spatial_filter}</FILTER>
        <INCLUDE>Deviation.Id</INCLUDE>
        <INCLUDE>Deviation.Header</INCLUDE>
        <INCLUDE>Deviation.Message</INCLUDE>
        <INCLUDE>Deviation.Geometry.Point.WGS84</INCLUDE>
        <INCLUDE>Deviation.Geometry.Line.WGS84</INCLUDE>
        <INCLUDE>Deviation.LocationDescriptor</INCLUDE>
        <INCLUDE>Deviation.StartTime</INCLUDE>
        <INCLUDE>Deviation.EndTime</INCLUDE>
        <INCLUDE>Deviation.SeverityCode</INCLUDE>
        <INCLUDE>Deviation.MessageType</INCLUDE>
    </QUERY>
</REQUEST>"""


def parse_wkt_geometry(wkt: str | None) -> dict[str, Any] | None:
    """Tolka Trafikverkets WKT-geometri (WGS84) till GeoJSON via shapely."""
    if not wkt:
        return None
    try:
        return mapping(shapely.from_wkt(wkt))
    except (ShapelyError, ValueError):
        logger.warning("Kunde inte tolka WKT-geometri: %s", wkt[:100])
        return None


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        logger.warning("Kunde inte tolka tidsstämpel: %s", value)
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def derive_status(start: datetime | None, end: datetime | None, now: datetime) -> ProjectStatus:
    """Härled status ur start- och sluttid relativt nu."""
    if start is not None and start > now:
        return ProjectStatus.PLANERAD
    if end is not None and end < now:
        return ProjectStatus.AVSLUTAD
    return ProjectStatus.PAGAENDE


def map_message_type(message_type: str | None) -> ProjectType:
    if not message_type:
        return ProjectType.OVRIGT
    return MESSAGE_TYPE_MAP.get(message_type, ProjectType.OVRIGT)


def _geometry_in_bbox(geometry: dict[str, Any], bbox: Bbox) -> bool:
    """Kontrollera att någon del av geometrin ligger i bbox (skyddsnät
    utöver API:ts spatiala filter)."""
    try:
        geom = shapely.geometry.shape(geometry)
    except (ShapelyError, ValueError):
        return False
    west, south, east, north = bbox
    return shapely.box(west, south, east, north).intersects(geom)


@register
class TrafikverketDataSource(DataSource):
    name = "trafikverket"
    display_name = "Trafikverket (trafikinformation)"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    async def fetch_infrastructure_projects(
        self, bbox: Bbox | None = None
    ) -> list[InfrastructureProjectIngest]:
        api_key = self._api_key or get_settings().trafikverket_api_key
        if not api_key:
            raise DataSourceError(self.name, "TRAFIKVERKET_API_KEY är inte satt i backendens miljö")

        xml_body = build_request_xml(api_key, bbox)

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    API_URL, content=xml_body, headers={"Content-Type": "text/xml"}
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise DataSourceError(self.name, f"API-anropet misslyckades: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise DataSourceError(self.name, "Svaret kunde inte tolkas som JSON") from exc

        return self._parse_response(data, bbox)

    def _parse_response(
        self, data: dict[str, Any], bbox: Bbox | None
    ) -> list[InfrastructureProjectIngest]:
        results: list[InfrastructureProjectIngest] = []
        now = datetime.now(UTC)

        result_blocks = data.get("RESPONSE", {}).get("RESULT", [])
        situations = result_blocks[0].get("Situation", []) if result_blocks else []

        for situation in situations:
            deviations = situation.get("Deviation", [])
            if not isinstance(deviations, list):
                deviations = [deviations]

            for deviation in deviations:
                if not deviation:
                    continue
                ingest = self._parse_deviation(deviation, now)
                if ingest is None:
                    continue
                if bbox and ingest.geometry and not _geometry_in_bbox(ingest.geometry, bbox):
                    continue
                results.append(ingest)

        logger.info("Hämtade %d objekt från Trafikverket", len(results))
        return results

    def _parse_deviation(
        self, deviation: dict[str, Any], now: datetime
    ) -> InfrastructureProjectIngest | None:
        external_id = deviation.get("Id")
        if not external_id:
            return None

        geom_data = deviation.get("Geometry") or {}
        geometry = parse_wkt_geometry(geom_data.get("Line", {}).get("WGS84")) or parse_wkt_geometry(
            geom_data.get("Point", {}).get("WGS84")
        )

        start = parse_timestamp(deviation.get("StartTime"))
        end = parse_timestamp(deviation.get("EndTime"))

        return InfrastructureProjectIngest(
            external_id=external_id,
            source=self.name,
            name=deviation.get("Header") or "Okänt objekt",
            description=deviation.get("Message"),
            project_type=map_message_type(deviation.get("MessageType")),
            status=derive_status(start, end, now),
            start_date=start.date() if start else None,
            end_date=end.date() if end else None,
            geometry=geometry,
            impact_radius_m=DEFAULT_IMPACT_RADIUS_M,
            metadata_json={
                "severity_code": deviation.get("SeverityCode"),
                "message_type": deviation.get("MessageType"),
                "location_descriptor": deviation.get("LocationDescriptor"),
            },
        )
