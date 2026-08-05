"""Datakälla: detaljplaner ur Lantmäteriets nationella geodataplattform (NGP).

Sök-API:t ("Geodatakatalog Sökning för detaljplan", STAC/OGC API
Features) är CC0 men kräver konsumentkonto via Geotorget. Med OAuth2-
uppgifter i miljön (LANTMATERIET_CONSUMER_KEY/SECRET) används det
riktiga API:t; utan används den publika sökproxy som Lantmäteriets
webbkarta (detaljplaner.lantmateriet.se) exponerar — samma backend och
svarsform, men odokumenterad och endast /search-vägen (verifierad
2026-08-05).

Viktigt om datat:
    - API:t bryter medvetet mot OAPIF-standarden: default-CRS är
      SWEREF 99 TM. WGS84 begärs explicit med crs-/bbox-crs-parametrarna.
    - Varje planbestämmelse är en egen feature — filtret
      ``feature.typ = detaljplan`` ger enbart planytorna.
    - NGP innehåller bara planer som kommunerna hunnit digitalisera
      (lagkrav för planer påbörjade efter 2022) — täckningen varierar
      kraftigt mellan kommuner.
    - Paginering är cursor-baserad (afterId = sista featurens id);
      en kort sida betyder sista sidan.
"""

import logging
import re
from datetime import date
from typing import Any

import httpx

from app.config import get_settings
from app.datasources.base import (
    Bbox,
    DataSource,
    DataSourceError,
    DetailPlanIngest,
    register,
)

logger = logging.getLogger(__name__)

CRS84_URI = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"

API_SEARCH_URL = (
    "https://api.lantmateriet.se/distribution/geodatakatalog/sokning/v1/detaljplan/v2/search"
)
TOKEN_URL = "https://api.lantmateriet.se/token"
# Publika sökproxyn bakom Lantmäteriets webbkarta — ingen nyckel krävs.
PROXY_SEARCH_URL = "https://detaljplaner.lantmateriet.se/api/detaljplan/sok/search"

PAGE_LIMIT = 1000
MAX_PAGES = 10

# Proxyn svarar med tom kropp på httpx standard-User-Agent (verifierat
# 2026-08-05) — identifiera appen ärligt i stället.
USER_AGENT = "Fastighetsvisualiserare/1.0"

_KOMMUN_SUFFIX_RE = re.compile(r"s? kommun$", re.IGNORECASE)


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _municipality_name(providers: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """(kommunnamn, kommunkod) ur providers-listan.

    Producentnamnet normaliseras ("Nacka kommun" → "Nacka") så att det
    följer samma form som fastigheternas kommunfält.
    """
    for provider in providers:
        if "producer" in (provider.get("roles") or []):
            name = (provider.get("name") or "").strip()
            return (_KOMMUN_SUFFIX_RE.sub("", name) or None, provider.get("kod"))
    return None, None


def build_search_body(bbox: Bbox | None, after_id: str | None) -> dict[str, Any]:
    """POST-kropp för /search: enbart planytor, WGS84-bbox, cursor."""
    body: dict[str, Any] = {
        "limit": PAGE_LIMIT,
        "query": {"feature.typ": {"eq": "detaljplan"}},
    }
    if bbox is not None:
        body["bbox"] = list(bbox)
        body["bbox-crs"] = CRS84_URI
    if after_id is not None:
        body["afterId"] = after_id
    return body


@register
class DetaljplanerDataSource(DataSource):
    name = "detaljplaner"
    display_name = "Lantmäteriet (detaljplaner)"

    def __init__(self, search_url: str | None = None) -> None:
        # Sätts i tester; annars väljs URL utifrån konfigurerade nycklar.
        self._search_url_override = search_url
        self.truncated = False

    async def fetch_detail_plans(self, bbox: Bbox | None = None) -> list[DetailPlanIngest]:
        self.truncated = False
        settings = get_settings()
        use_official = bool(
            settings.lantmateriet_consumer_key and settings.lantmateriet_consumer_secret
        )

        async with httpx.AsyncClient(timeout=60.0, headers={"User-Agent": USER_AGENT}) as client:
            headers: dict[str, str] = {}
            if self._search_url_override:
                search_url = self._search_url_override
            elif use_official:
                search_url = API_SEARCH_URL
                headers["Authorization"] = f"Bearer {await self._fetch_token(client, settings)}"
            else:
                search_url = PROXY_SEARCH_URL
                logger.info("Inga Lantmäteriet-nycklar konfigurerade — använder publika sökproxyn")

            plans: list[DetailPlanIngest] = []
            seen: set[str] = set()
            after_id: str | None = None
            for _ in range(MAX_PAGES):
                features = await self._fetch_page(client, search_url, headers, bbox, after_id)
                for feature in features:
                    ingest = self._build_ingest(feature)
                    if ingest is not None and ingest.external_id not in seen:
                        seen.add(ingest.external_id)
                        plans.append(ingest)
                if len(features) < PAGE_LIMIT:
                    break
                after_id = features[-1].get("id")
                if not after_id:
                    break
            else:
                logger.warning(
                    "Detaljplaner: sidgränsen (%d sidor) nådd — trunkerad hämtning; "
                    "kör igen med snävare bbox",
                    MAX_PAGES,
                )
                self.truncated = True

        logger.info("Hämtade %d detaljplaner från NGP", len(plans))
        return plans

    async def _fetch_token(self, client: httpx.AsyncClient, settings: Any) -> str:
        """OAuth2 client credentials mot Lantmäteriets API-portal."""
        try:
            response = await client.post(
                TOKEN_URL,
                auth=(settings.lantmateriet_consumer_key, settings.lantmateriet_consumer_secret),
                data={"grant_type": "client_credentials"},
            )
            response.raise_for_status()
            token = response.json().get("access_token")
        except httpx.HTTPError as exc:
            raise DataSourceError(self.name, f"Tokenanropet misslyckades: {exc}") from exc
        except ValueError as exc:
            raise DataSourceError(self.name, "Tokensvaret kunde inte tolkas som JSON") from exc
        if not token:
            raise DataSourceError(self.name, "Tokensvaret saknade access_token")
        return token

    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        search_url: str,
        headers: dict[str, str],
        bbox: Bbox | None,
        after_id: str | None,
    ) -> list[dict[str, Any]]:
        try:
            response = await client.post(
                search_url,
                params={"crs": CRS84_URI},
                headers=headers,
                json=build_search_body(bbox, after_id),
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise DataSourceError(
                    self.name,
                    "Åtkomst nekad (401). Skaffa konsumentkonto via Geotorget och sätt "
                    "LANTMATERIET_CONSUMER_KEY/SECRET, eller försök igen senare om "
                    "den publika proxyn ändrats.",
                ) from exc
            raise DataSourceError(self.name, f"API-anropet misslyckades: {exc}") from exc
        except httpx.HTTPError as exc:
            raise DataSourceError(self.name, f"API-anropet misslyckades: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise DataSourceError(self.name, "Svaret kunde inte tolkas som JSON") from exc

        features = data.get("features") if isinstance(data, dict) else None
        if not isinstance(features, list):
            raise DataSourceError(self.name, f"Oväntad svarsform: {str(data)[:200]}")
        return [f for f in features if isinstance(f, dict)]

    def _build_ingest(self, feature: dict[str, Any]) -> DetailPlanIngest | None:
        props = feature.get("properties") or {}
        # Skyddsnät: query-filtret ska redan ha sållat, men proxyn är
        # odokumenterad — släpp aldrig igenom enskilda bestämmelser.
        if (props.get("feature") or {}).get("typ") != "detaljplan":
            return None

        detaljplan = props.get("detaljplan") or {}
        external_id = feature.get("id") or detaljplan.get("objektidentitet")
        if not external_id:
            logger.warning("Hoppar över detaljplan utan objektidentitet")
            return None

        geometry = feature.get("geometry")
        if geometry is None:
            logger.warning("Hoppar över detaljplan %s: ingen geometri", external_id)
            return None

        municipality, municipality_code = _municipality_name(props.get("providers") or [])
        name = (
            (detaljplan.get("namn") or "").strip()
            or (props.get("title") or "").strip()
            or (detaljplan.get("beteckning") or "").strip()
            or "Detaljplan utan namn"
        )

        return DetailPlanIngest(
            external_id=str(external_id),
            source=self.name,
            name=name,
            plan_number=detaljplan.get("beteckning"),
            status=detaljplan.get("status"),
            municipality=municipality,
            adopted_date=_parse_date(detaljplan.get("datumLagakraft")),
            geometry=geometry,
            metadata_json={
                "plantyp": detaljplan.get("typ"),
                "kommunkod": municipality_code,
                "datum_paborjat": detaljplan.get("datumPaborjat"),
                "datum_statusforandring": detaljplan.get("datumStatusforandring"),
                "anvandbarhet": detaljplan.get("anvandbarhet"),
            },
        )
