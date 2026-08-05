import json
import logging
import re

import httpx

from config import settings
from services.base_datasource import DataSource

logger = logging.getLogger(__name__)

API_URL = "https://api.trafikinfo.trafikverket.se/v2/data.json"

XML_TEMPLATE = """<REQUEST>
    <LOGIN authenticationkey="{api_key}" />
    <QUERY objecttype="Situation" schemaversion="1.5" limit="500">
        <FILTER />
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

# Map Trafikverket MessageType to our project_type values
MESSAGE_TYPE_MAP = {
    "Vägarbete": "väg",
    "Trafikmeddelande": "väg",
    "Olycka": "väg",
    "Hinder": "väg",
    "Järnväg": "järnväg",
    "Kollektivtrafik": "kollektivtrafik",
    "Bro": "bro",
    "Tunnel": "tunnel",
    "Cykelväg": "cykelväg",
}


def _parse_wgs84_geometry(wgs84_str: str) -> dict | None:
    """Parse a WGS84 geometry string into GeoJSON.

    Handles formats like:
        "POINT (18.07 59.33)"
        "LINESTRING (18.07 59.33, 18.08 59.34)"
        "MULTIPOINT ((18.07 59.33), (18.08 59.34))"
    """
    if not wgs84_str:
        return None

    wgs84_str = wgs84_str.strip()

    # Match POINT
    point_match = re.match(
        r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)", wgs84_str
    )
    if point_match:
        lng, lat = float(point_match.group(1)), float(point_match.group(2))
        return {"type": "Point", "coordinates": [lng, lat]}

    # Match LINESTRING
    line_match = re.match(r"LINESTRING\s*\((.+)\)", wgs84_str)
    if line_match:
        coords_str = line_match.group(1)
        coords = []
        for pair in coords_str.split(","):
            parts = pair.strip().split()
            if len(parts) == 2:
                coords.append([float(parts[0]), float(parts[1])])
        if coords:
            return {"type": "LineString", "coordinates": coords}

    # Match MULTIPOINT
    multi_match = re.match(r"MULTIPOINT\s*\((.+)\)", wgs84_str)
    if multi_match:
        coords_str = multi_match.group(1)
        coords = []
        for pair_match in re.finditer(r"\(\s*([-\d.]+)\s+([-\d.]+)\s*\)", coords_str):
            coords.append([float(pair_match.group(1)), float(pair_match.group(2))])
        if coords:
            if len(coords) == 1:
                return {"type": "Point", "coordinates": coords[0]}
            return {"type": "MultiPoint", "coordinates": coords}

    logger.warning("Could not parse WGS84 geometry: %s", wgs84_str[:100])
    return None


def _map_message_type(message_type: str | None) -> str:
    """Map Trafikverket MessageType to our project_type."""
    if not message_type:
        return "övrigt"
    return MESSAGE_TYPE_MAP.get(message_type, "övrigt")


class TrafikverketDataSource(DataSource):
    """Data source for Trafikverket's open traffic information API."""

    @property
    def source_name(self) -> str:
        return "trafikverket"

    async def fetch_infrastructure_projects(
        self, bbox: tuple[float, float, float, float] | None = None
    ) -> list[dict]:
        """Fetch deviation/situation data from Trafikverket API."""
        api_key = settings.trafikverket_api_key
        if not api_key:
            logger.warning("No Trafikverket API key configured, skipping fetch")
            return []

        xml_body = XML_TEMPLATE.format(api_key=api_key)

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    API_URL,
                    content=xml_body,
                    headers={"Content-Type": "text/xml"},
                )
                response.raise_for_status()
            except httpx.HTTPError as e:
                logger.error("Trafikverket API request failed: %s", e)
                return []

        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.error("Failed to decode Trafikverket API response as JSON")
            return []

        results = []
        situations = (
            data.get("RESPONSE", {})
            .get("RESULT", [{}])[0]
            .get("Situation", [])
        )

        for situation in situations:
            deviations = situation.get("Deviation", [])
            if not isinstance(deviations, list):
                deviations = [deviations]

            for deviation in deviations:
                if not deviation:
                    continue

                # Extract geometry (prefer line, fall back to point)
                geometry = None
                geom_data = deviation.get("Geometry", {})
                if geom_data:
                    line_wgs84 = geom_data.get("Line", {}).get("WGS84")
                    point_wgs84 = geom_data.get("Point", {}).get("WGS84")

                    if line_wgs84:
                        geometry = _parse_wgs84_geometry(line_wgs84)
                    elif point_wgs84:
                        geometry = _parse_wgs84_geometry(point_wgs84)

                # Filter by bbox if specified
                if bbox and geometry:
                    west, south, east, north = bbox
                    coords = geometry.get("coordinates", [])
                    if geometry["type"] == "Point":
                        lng, lat = coords
                        if not (west <= lng <= east and south <= lat <= north):
                            continue
                    # For lines/multipoints, check if any coord is in bbox
                    elif isinstance(coords[0], list):
                        in_bbox = any(
                            west <= c[0] <= east and south <= c[1] <= north
                            for c in coords
                        )
                        if not in_bbox:
                            continue

                project = {
                    "external_id": deviation.get("Id"),
                    "source": "trafikverket",
                    "name": deviation.get("Header", "Okänt projekt"),
                    "description": deviation.get("Message"),
                    "project_type": _map_message_type(
                        deviation.get("MessageType")
                    ),
                    "status": "pågående",
                    "start_date": deviation.get("StartTime"),
                    "end_date": deviation.get("EndTime"),
                    "geometry": geometry,
                    "metadata_json": {
                        "severity_code": deviation.get("SeverityCode"),
                        "message_type": deviation.get("MessageType"),
                        "location_descriptor": deviation.get(
                            "LocationDescriptor"
                        ),
                    },
                }
                results.append(project)

        logger.info(
            "Fetched %d infrastructure projects from Trafikverket", len(results)
        )
        return results

    async def fetch_properties(
        self, bbox: tuple[float, float, float, float] | None = None
    ) -> list[dict]:
        """Trafikverket does not provide property data."""
        return []
