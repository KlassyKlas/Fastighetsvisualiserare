"""Datakälla: DeSO-områden med demografi från SCB (öppna data, CC0).

Två öppna SCB-tjänster kombineras (ingen nyckel krävs, verifierat
2026-08-05):

    - Gränserna: GeoServer-WFS:en ``geodata.scb.se`` levererar DeSO 2025
      (6160 områden) som GeoJSON direkt i WGS84 (srsName=EPSG:4326).
      Polygonerna förenklas vid ingest (~10 m) — de är statistikytor,
      inte juridiska gränser, och full upplösning är brus på en webbkarta.
    - Statistiken: PXWeb-API:t v1. Befolkning, medelinkomst och
      utbildningsnivå hämtas med ett anrop per tabell (alla DeSO ryms
      inom cellgränsen på 150 000).

Vintage-fällan: PXWeb:s regionkoder för DeSO 2025 har suffixet
``_DeSO2025`` (t.ex. "0180C1010_DeSO2025"); de osuffixade koderna avser
2018-indelningen och ger TYSTA NOLLOR för nya årgångar. WFS:ens
``desokod`` saknar suffix — matchning sker via suffixstrykning.
Kommunnamn finns inte i WFS-attributen; de slås upp ur PXWeb-tabellens
regionmetadata (fyrställiga koder = kommuner).

Rate limit: 30 anrop/10 s — källan gör ~10 WFS-sidor + 4 PXWeb-anrop.
"""

import logging
from typing import Any

import httpx
import shapely
from shapely.errors import ShapelyError
from shapely.geometry import mapping, shape

from app.datasources.base import Bbox, DataSource, DataSourceError, DesoAreaIngest, register

logger = logging.getLogger(__name__)

WFS_URL = "https://geodata.scb.se/geoserver/stat/ows"
WFS_LAYER = "stat:DeSO_2025"
WFS_PAGE_SIZE = 1000
WFS_MAX_PAGES = 10  # 6160 områden → 7 sidor; taket är ett skyddsnät

PXWEB_BASE = "https://api.scb.se/OV0104/v1/doris/sv/ssd"
POPULATION_TABLE = f"{PXWEB_BASE}/BE/BE0101/BE0101Y/FolkmDesoAldKon"
INCOME_TABLE = f"{PXWEB_BASE}/HE/HE0110/HE0110I/Tab2InkDesoRegso"
EDUCATION_TABLE = f"{PXWEB_BASE}/UF/UF0506/UF0506D/UtbSUNBefDesoRegsoN"

# PXWeb-koder, verifierade mot tabellernas metadata 2026-08-05
DESO2025_SUFFIX = "_DeSO2025"
NETTOINKOMST = "240"  # Inkomstkomponenter: nettoinkomst
MEDELVARDE_TKR = "000008A4"  # ContentsCode: medelvärde för samtliga, tkr
EFTERGYMNASIALA = ("5", "6")  # eftergymnasial <3 år respektive ≥3 år

# ~10 m — samma storleksordning som påverkanszonernas förenkling
FORENKLING_GRADER = 0.0001


def _json_stat2_values(data: dict[str, Any], region_dim: str = "Region") -> dict[str, list[Any]]:
    """Värdena per region ur ett json-stat2-svar.

    json-stat2 lagrar värdena radvis i dimensionsordning. När Region är
    första icke-triviala dimensionen (våra tre tabeller har Region
    först) är varje regions värden ett sammanhängande block, ordnat
    efter de efterföljande dimensionerna.
    """
    ids: list[str] = data["id"]
    sizes: list[int] = data["size"]
    values: list[Any] = data["value"]

    region_pos = ids.index(region_dim)
    leading = 1
    for size in sizes[:region_pos]:
        leading *= size
    if leading != 1:
        raise DataSourceError("scb_deso", f"Region är inte första icke-triviala dimensionen: {ids}")
    block = 1
    for size in sizes[region_pos + 1 :]:
        block *= size

    region_index: dict[str, int] = data["dimension"][region_dim]["category"]["index"]
    return {code: values[idx * block : (idx + 1) * block] for code, idx in region_index.items()}


@register
class ScbDesoDataSource(DataSource):
    name = "scb_deso"
    display_name = "SCB (demografi per DeSO)"

    def __init__(self, wfs_url: str | None = None, pxweb_base: str | None = None) -> None:
        # Sätts i tester
        self._wfs_url = wfs_url or WFS_URL
        base = pxweb_base or PXWEB_BASE
        self._population_table = POPULATION_TABLE.replace(PXWEB_BASE, base)
        self._income_table = INCOME_TABLE.replace(PXWEB_BASE, base)
        self._education_table = EDUCATION_TABLE.replace(PXWEB_BASE, base)
        self.truncated = False

    async def fetch_deso_areas(self, bbox: Bbox | None = None) -> list[DesoAreaIngest]:
        self.truncated = False
        async with httpx.AsyncClient(
            timeout=120.0, headers={"User-Agent": "Fastighetsvisualiserare/1.0"}
        ) as client:
            raw_areas = await self._fetch_boundaries(client, bbox)
            if not raw_areas:
                return []

            deso_codes = [code for code, _, _ in raw_areas]
            population, population_year, kommun_names = await self._fetch_population(
                client, deso_codes
            )
            income, income_year = await self._fetch_income(client, deso_codes)
            education_share, education_year = await self._fetch_education(client, deso_codes)

        areas = []
        for deso_code, props, geometry in raw_areas:
            kommunkod = props.get("kommunkod")
            areas.append(
                DesoAreaIngest(
                    deso_code=deso_code,
                    municipality_code=kommunkod,
                    municipality=kommun_names.get(kommunkod or ""),
                    population=population.get(deso_code),
                    population_year=population_year,
                    mean_income_sek=income.get(deso_code),
                    higher_education_share=education_share.get(deso_code),
                    geometry=geometry,
                    stats_json={
                        "regso_kod": props.get("regsokod"),
                        "lanskod": props.get("lanskod"),
                        "inkomstar": income_year,
                        "utbildningsar": education_year,
                        "indelning": "DeSO 2025",
                    },
                )
            )
        logger.info("Hämtade %d DeSO-områden från SCB", len(areas))
        return areas

    async def _fetch_boundaries(
        self, client: httpx.AsyncClient, bbox: Bbox | None
    ) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
        """(desokod, attribut, förenklad geometri) för alla områden.

        WFS:en bbox-filtreras inte serverledes (axelordningskaos i WFS
        2.0) — allt hämtas och filtreras klientledes; det är ~40 MB en
        gång per synk och undviker en klassisk felkälla.
        """
        results: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        clip = shapely.box(*bbox) if bbox is not None else None

        start_index = 0
        for _ in range(WFS_MAX_PAGES):
            params = {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": WFS_LAYER,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": str(WFS_PAGE_SIZE),
                "startIndex": str(start_index),
            }
            try:
                response = await client.get(self._wfs_url, params=params)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as exc:
                raise DataSourceError(self.name, f"WFS-anropet misslyckades: {exc}") from exc
            except ValueError as exc:
                raise DataSourceError(self.name, "WFS-svaret kunde inte tolkas som JSON") from exc

            features = data.get("features") or []
            for feature in features:
                parsed = self._parse_boundary(feature, clip)
                if parsed is not None:
                    results.append(parsed)

            if len(features) < WFS_PAGE_SIZE:
                return results
            start_index += len(features)

        logger.warning("SCB WFS: sidgränsen nådd — trunkerad hämtning")
        self.truncated = True
        return results

    def _parse_boundary(
        self, feature: dict[str, Any], clip: shapely.Geometry | None
    ) -> tuple[str, dict[str, Any], dict[str, Any]] | None:
        props = feature.get("properties") or {}
        deso_code = props.get("desokod")
        if not deso_code:
            logger.warning("Hoppar över DeSO-yta utan desokod")
            return None
        try:
            geom = shape(feature.get("geometry"))
            if clip is not None and not clip.intersects(geom):
                return None
            simplified = geom.simplify(FORENKLING_GRADER, preserve_topology=True)
            if not simplified.is_valid:
                simplified = shapely.make_valid(simplified)
        except (ShapelyError, ValueError, KeyError, TypeError, AttributeError):
            logger.warning("Hoppar över DeSO %s: otolkbar geometri", deso_code)
            return None
        if simplified.is_empty or simplified.geom_type not in ("Polygon", "MultiPolygon"):
            logger.warning("Hoppar över DeSO %s: degenererad geometri", deso_code)
            return None
        return deso_code, props, mapping(simplified)

    async def _pxweb_metadata(self, client: httpx.AsyncClient, table_url: str) -> dict[str, Any]:
        try:
            response = await client.get(table_url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise DataSourceError(self.name, f"PXWeb-metadata misslyckades: {exc}") from exc
        except ValueError as exc:
            raise DataSourceError(
                self.name, "PXWeb-metadatasvaret kunde inte tolkas som JSON"
            ) from exc

    async def _pxweb_data(
        self, client: httpx.AsyncClient, table_url: str, query: list[dict[str, Any]]
    ) -> dict[str, Any]:
        try:
            response = await client.post(
                table_url, json={"query": query, "response": {"format": "json-stat2"}}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise DataSourceError(self.name, f"PXWeb-anropet misslyckades: {exc}") from exc
        except ValueError as exc:
            raise DataSourceError(self.name, "PXWeb-svaret kunde inte tolkas som JSON") from exc

    @staticmethod
    def _latest_year(metadata: dict[str, Any]) -> str:
        for variable in metadata.get("variables", []):
            if variable.get("code") == "Tid":
                values = variable.get("values") or []
                if values:
                    return values[-1]
        raise DataSourceError("scb_deso", "PXWeb-tabellen saknar Tid-variabel")

    @staticmethod
    def _item_selection(code: str, values: list[str]) -> dict[str, Any]:
        return {"code": code, "selection": {"filter": "item", "values": values}}

    async def _fetch_population(
        self, client: httpx.AsyncClient, deso_codes: list[str]
    ) -> tuple[dict[str, int], int, dict[str, str]]:
        """Befolkning per DeSO + kommunnamnstabell ur regionmetadatan."""
        metadata = await self._pxweb_metadata(client, self._population_table)
        year = self._latest_year(metadata)

        kommun_names: dict[str, str] = {}
        for variable in metadata.get("variables", []):
            if variable.get("code") == "Region":
                for value, text in zip(
                    variable.get("values", []), variable.get("valueTexts", []), strict=False
                ):
                    if len(value) == 4 and value.isdigit():
                        # valueText har kodprefix: "0180 Stockholm" → "Stockholm"
                        kommun_names[value] = text.removeprefix(value).strip()

        data = await self._pxweb_data(
            client,
            self._population_table,
            [
                self._item_selection("Region", [c + DESO2025_SUFFIX for c in deso_codes]),
                self._item_selection("Alder", ["totalt"]),
                self._item_selection("Kon", ["1+2"]),
                self._item_selection("Tid", [year]),
            ],
        )
        per_region = _json_stat2_values(data)
        population = {
            code.removesuffix(DESO2025_SUFFIX): int(values[0])
            for code, values in per_region.items()
            if values and values[0] is not None
        }
        return population, int(year), kommun_names

    async def _fetch_income(
        self, client: httpx.AsyncClient, deso_codes: list[str]
    ) -> tuple[dict[str, int], int]:
        """Medelvärde av nettoinkomst (tkr → kr) per DeSO."""
        metadata = await self._pxweb_metadata(client, self._income_table)
        year = self._latest_year(metadata)

        data = await self._pxweb_data(
            client,
            self._income_table,
            [
                self._item_selection("Region", [c + DESO2025_SUFFIX for c in deso_codes]),
                self._item_selection("Inkomstkomponenter", [NETTOINKOMST]),
                self._item_selection("Kon", ["1+2"]),
                self._item_selection("ContentsCode", [MEDELVARDE_TKR]),
                self._item_selection("Tid", [year]),
            ],
        )
        per_region = _json_stat2_values(data)
        income = {
            code.removesuffix(DESO2025_SUFFIX): round(values[0] * 1000)
            for code, values in per_region.items()
            if values and values[0] is not None
        }
        return income, int(year)

    async def _fetch_education(
        self, client: httpx.AsyncClient, deso_codes: list[str]
    ) -> tuple[dict[str, float], int]:
        """Andel 25–64 år med eftergymnasial utbildning per DeSO."""
        metadata = await self._pxweb_metadata(client, self._education_table)
        year = self._latest_year(metadata)

        niva_codes = ["21", "3+4", "5", "6", "US"]
        data = await self._pxweb_data(
            client,
            self._education_table,
            [
                self._item_selection("Region", [c + DESO2025_SUFFIX for c in deso_codes]),
                self._item_selection("UtbildningsNiva", niva_codes),
                self._item_selection("Tid", [year]),
            ],
        )

        ids: list[str] = data["id"]
        niva_index: dict[str, int] = data["dimension"]["UtbildningsNiva"]["category"]["index"]
        per_region = _json_stat2_values(data)

        # per_region ger värdena i UtbildningsNiva-ordning endast om
        # UtbildningsNiva är den sista icke-triviala dimensionen —
        # verifiera antagandet i stället för att lita tyst på det.
        niva_pos = ids.index("UtbildningsNiva")
        region_pos = ids.index("Region")
        if niva_pos < region_pos:
            raise DataSourceError(self.name, "Oväntad dimensionsordning i utbildningstabellen")

        shares: dict[str, float] = {}
        for code, values in per_region.items():
            total = sum(v for v in values if v is not None)
            if total <= 0:
                continue
            higher = sum(
                values[idx]
                for niva, idx in niva_index.items()
                if niva in EFTERGYMNASIALA and idx < len(values) and values[idx] is not None
            )
            shares[code.removesuffix(DESO2025_SUFFIX)] = round(higher / total, 4)
        return shares, int(year)
