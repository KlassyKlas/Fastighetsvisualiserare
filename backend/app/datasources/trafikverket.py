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
# Situation 1.6 i namespace Road.TrafficInfo är enda publicerade versionen
# sedan 2026-03-04 — äldre schemaversioner (1.5 utan namespace) är nedsläckta.
NAMESPACE = "Road.TrafficInfo"
SCHEMA_VERSION = "1.6"
REQUEST_LIMIT = 500
DEFAULT_IMPACT_RADIUS_M = 1000.0

# Trafikverkets faktiska MessageType-värden i Situation 1.6 →
# våra projekttyper. Allt okänt faller tillbaka på "övrigt".
MESSAGE_TYPE_MAP: dict[str, ProjectType] = {
    "Vägarbete": ProjectType.VAG,
    "Trafikmeddelande": ProjectType.VAG,
    "Olycka": ProjectType.VAG,
    "Hinder": ProjectType.VAG,
    "Restriktion": ProjectType.VAG,
    "Viktig trafikinformation": ProjectType.OVRIGT,
    "Färjor": ProjectType.OVRIGT,
}


def build_request_xml(api_key: str, bbox: Bbox | None = None, changeid: str = "0") -> str:
    """Bygg API-frågan. Med bbox filtreras spatialt redan på serversidan.

    INTERSECTS (inte WITHIN): WITHIN matchar bara geometrier som ligger
    helt inom rutan och tappar t.ex. vägsträckor som korsar kanten.

    changeid ger sidvis hämtning: första frågan skickar "0", följande
    frågor skickar LASTCHANGEID ur föregående svar tills färre än
    REQUEST_LIMIT situationer returneras.
    """
    spatial_filter = ""
    if bbox is not None:
        west, south, east, north = bbox
        spatial_filter = (
            f'<INTERSECTS name="Deviation.Geometry.WGS84" shape="box" '
            f'value="{west} {south}, {east} {north}" />'
        )

    query_attrs = (
        f'namespace="{NAMESPACE}" objecttype="Situation" '
        f'schemaversion="{SCHEMA_VERSION}" limit="{REQUEST_LIMIT}" '
        f'changeid="{escape(changeid, {chr(34): "&quot;"})}"'
    )
    return f"""<REQUEST>
    <LOGIN authenticationkey="{escape(api_key, {'"': "&quot;"})}" />
    <QUERY {query_attrs}>
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
        <INCLUDE>Deviation.Suspended</INCLUDE>
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


def _extract_result_block(data: dict[str, Any]) -> tuple[list[Any], str | None]:
    """Plocka ut situationslistan och LASTCHANGEID ur ett API-svar.

    Tål null-värden på varje nivå — API:t serialiserar ibland tomma
    fält som JSON null i stället för att utelämna dem.
    """
    result_blocks = (data.get("RESPONSE") or {}).get("RESULT") or []
    if not result_blocks or not isinstance(result_blocks[0], dict):
        return [], None
    block = result_blocks[0]
    situations = block.get("Situation") or []
    if not isinstance(situations, list):
        situations = [situations]
    last_changeid = (block.get("INFO") or {}).get("LASTCHANGEID")
    return situations, str(last_changeid) if last_changeid is not None else None


# Skyddstak för pagineringsloopen: 20 sidor à 500 situationer
MAX_PAGES = 20


@register
class TrafikverketDataSource(DataSource):
    name = "trafikverket"
    display_name = "Trafikverket (trafikinformation)"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key
        self.truncated = False

    async def fetch_infrastructure_projects(
        self, bbox: Bbox | None = None
    ) -> list[InfrastructureProjectIngest]:
        api_key = self._api_key or get_settings().trafikverket_api_key
        if not api_key:
            raise DataSourceError(self.name, "TRAFIKVERKET_API_KEY är inte satt i backendens miljö")

        self.truncated = False
        results: list[InfrastructureProjectIngest] = []
        changeid = "0"

        async with httpx.AsyncClient(timeout=30.0) as client:
            for _ in range(MAX_PAGES):
                data = await self._request(client, api_key, bbox, changeid)
                situations, last_changeid = _extract_result_block(data)
                results.extend(self._parse_situations(situations, bbox))

                # limit gäller antal Situation-objekt — jämför mot råantalet,
                # inte mot antalet tolkade deviations
                if len(situations) < REQUEST_LIMIT:
                    break
                if not last_changeid or last_changeid == changeid:
                    logger.warning(
                        "Trafikverket: full sida utan användbart LASTCHANGEID — "
                        "hämtningen kan vara ofullständig"
                    )
                    self.truncated = True
                    break
                changeid = last_changeid
            else:
                logger.warning(
                    "Trafikverket: sidgränsen (%d sidor) nådd — hämtningen trunkerad",
                    MAX_PAGES,
                )
                self.truncated = True

        logger.info("Hämtade %d objekt från Trafikverket", len(results))
        return results

    async def _request(
        self, client: httpx.AsyncClient, api_key: str, bbox: Bbox | None, changeid: str
    ) -> dict[str, Any]:
        xml_body = build_request_xml(api_key, bbox, changeid)
        try:
            response = await client.post(
                API_URL, content=xml_body, headers={"Content-Type": "text/xml"}
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DataSourceError(self.name, f"API-anropet misslyckades: {exc}") from exc

        try:
            return response.json()
        except ValueError as exc:
            raise DataSourceError(self.name, "Svaret kunde inte tolkas som JSON") from exc

    def _parse_response(
        self, data: dict[str, Any], bbox: Bbox | None
    ) -> list[InfrastructureProjectIngest]:
        """Tolka ett enskilt API-svar (används även direkt i tester)."""
        situations, _ = _extract_result_block(data)
        return self._parse_situations(situations, bbox)

    def _parse_situations(
        self, situations: list[Any], bbox: Bbox | None
    ) -> list[InfrastructureProjectIngest]:
        results: list[InfrastructureProjectIngest] = []
        now = datetime.now(UTC)

        for situation in situations:
            if not isinstance(situation, dict):
                continue
            deviations = situation.get("Deviation") or []
            if not isinstance(deviations, list):
                deviations = [deviations]

            for deviation in deviations:
                if not isinstance(deviation, dict):
                    continue
                ingest = self._parse_deviation(deviation, now)
                if ingest is None:
                    continue
                if bbox and ingest.geometry and not _geometry_in_bbox(ingest.geometry, bbox):
                    continue
                results.append(ingest)

        return results

    def _parse_deviation(
        self, deviation: dict[str, Any], now: datetime
    ) -> InfrastructureProjectIngest | None:
        external_id = deviation.get("Id")
        if not external_id:
            return None

        # "or {}" på varje nivå: API:t kan serialisera Line/Point som null
        geom_data = deviation.get("Geometry") or {}
        geometry = parse_wkt_geometry(
            (geom_data.get("Line") or {}).get("WGS84")
        ) or parse_wkt_geometry((geom_data.get("Point") or {}).get("WGS84"))

        start = parse_timestamp(deviation.get("StartTime"))
        end = parse_timestamp(deviation.get("EndTime"))

        # Suspended (nytt i 1.6): tillfälligt pausade arbeten, t.ex. över
        # semestern. Ett pausat arbete med framtida återstart är i praktiken
        # planerat snarare än pågående.
        suspended = bool(deviation.get("Suspended"))
        status = derive_status(start, end, now)
        if suspended and status == ProjectStatus.PAGAENDE:
            status = ProjectStatus.PLANERAD

        return InfrastructureProjectIngest(
            external_id=external_id,
            source=self.name,
            name=deviation.get("Header") or "Okänt objekt",
            description=deviation.get("Message"),
            project_type=map_message_type(deviation.get("MessageType")),
            status=status,
            start_date=start.date() if start else None,
            end_date=end.date() if end else None,
            geometry=geometry,
            impact_radius_m=DEFAULT_IMPACT_RADIUS_M,
            metadata_json={
                "severity_code": deviation.get("SeverityCode"),
                "message_type": deviation.get("MessageType"),
                "location_descriptor": deviation.get("LocationDescriptor"),
                "suspended": suspended,
            },
        )
