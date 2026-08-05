"""Datakälla: Trafikverkets investeringsprojekt ur nationell plan.

Trafikinfo-API:t (Situation m.fl.) innehåller inga investeringsprojekt —
modellförteckningens samtliga 74 objekttyper är operativ trafikdata
(verifierat 2026-08-05). Projektkorridorerna hämtas i stället från
Trafikverkets öppna riksintressetjänst (ArcGIS REST, ingen nyckel krävs):
lagren för planerade/framtida väg- och järnvägsanläggningar, som täcker
planens stora namngivna objekt (Ostlänken, Norrbotniabanan, Förbifart
Stockholm m.fl.) som korridorpolygoner i WGS84.

Kostnad och fas kommer ur Bilaga 1 till fastställd nationell plan
2026–2037 via den genererade tabellen ``nationell_plan_bilaga1.json``
(se ``scripts/import_bilaga1.py``). Kopplingen korridor → planobjekt är
handkurerad i ``BILAGA1_KOPPLING`` — automatisk namnmatchning gav fel
träffar (t.ex. Förbifart Stockholm → en följdinvestering) och fel
kostnadsuppgifter är värre än inga i ett investeringsverktyg.

Tjänstnamnet är versionerat (``Riksintressen_Prod_2025_01``) och kan
bytas vid nya riksintressebeslut. Aktuell adress löses därför upp via
302-redirecten från den stabila WMS-ingången; misslyckas det används
senast kända adress.
"""

import logging
import re
from functools import cache
from json import JSONDecodeError, loads
from pathlib import Path
from typing import Any, NamedTuple

import httpx
import shapely
from shapely.errors import ShapelyError
from shapely.geometry import mapping, shape

from app.datasources.base import (
    Bbox,
    DataSource,
    DataSourceError,
    InfrastructureProjectIngest,
    register,
)
from app.domain import ProjectStatus, ProjectType

logger = logging.getLogger(__name__)

# Stabil ingång vars redirect pekar ut den aktuella versionerade tjänsten.
REDIRECT_URL = "https://geo-ri.trafikverket.se/MapService/wms.axd/Riksintressen"
# Senast kända tjänstadress — reservväg om upplösningen misslyckas.
DEFAULT_SERVICE_URL = (
    "https://vektor-pr.trafikverket.se/gis/rest/services/"
    "Riksintressen/Riksintressen_Prod_2025_01/MapServer"
)
_SERVICE_PATH_RE = re.compile(r"^https://([^/]+)/gis/services/(Riksintressen/[^/]+/MapServer)")

# Tjänstens maxRecordCount är 2000 — hämtningen pagineras med resultOffset.
REQUEST_LIMIT = 2000
MAX_PAGES = 10

BILAGA1_PATH = Path(__file__).parent / "nationell_plan_bilaga1.json"

# Korridorerna är redan markanspråk — radien läggs ovanpå som
# påverkanszon. Järnvägar påverkar fastighetsvärden i ett större omland
# (stationslägen, buller) än vägobjekt.
IMPACT_RADIUS_M = {ProjectType.JARNVAG: 3000.0, ProjectType.VAG: 2000.0}


class Lager(NamedTuple):
    """Ett riksintresselager i tjänsten och hur det mappas till domänen."""

    lager_id: int
    projekttyp: ProjectType
    tidsperspektiv: str  # "planerad" eller "framtida"


LAGER: list[Lager] = [
    Lager(22, ProjectType.JARNVAG, "planerad"),
    Lager(23, ProjectType.JARNVAG, "framtida"),
    Lager(32, ProjectType.VAG, "planerad"),
    Lager(33, ProjectType.VAG, "framtida"),
]

# Handkurerad koppling (GenNamn, SpecNamn) → objekt-id i Bilaga 1.
# None betyder "granskad 2026-08-05: har ingen motsvarighet bland de
# namngivna objekten i plan 2026–2037" (t.ex. redan öppnade objekt,
# senare etapper eller korridorer utan finansiering i planen).
# Okända nycklar (nya korridorer i tjänsten) får helt enkelt ingen
# Bilaga 1-berikning. OBS: riksintressedatat stavar "Norrbottniabanan"
# med dubbelt t; Bilaga 1 skriver "Norrbotniabanan".
BILAGA1_KOPPLING: dict[tuple[str, str], str | None] = {
    # Järnväg, planerad (lager 22)
    ("Alvesta triangelspår", ""): "JSY1820",
    ("Anslutning till Gävle hamn", ""): None,
    ("Bergslagsbanan", "Falun-Borlänge"): None,  # omdragningen finns inte i planen
    ("Byarum - Tenhult", ""): None,  # del av ny stambana, ej i plan 2026–2037
    ("Godsstråket genom Bergslagen", "Hallsberg - Stenkumla"): "BVST030c",
    ("Godsstråket genom Bergslagen", "Jakobshyttan-Degerön"): None,  # byggd, ej namngiven längre
    ("Malmbanan", "Kiruna station samt anslutning"): "JN1804a",
    ("Norrbottniabanan", "Dåva-Skellefteå"): "YSN001a",
    ("Norrbottniabanan", "Skellefteå-Luleå"): "JN2201",
    ("Norrbottniabanan", "Umeå-Dåva"): "YSN001b",
    ("Ostkustbanan", "Dingersjö-Kubikenborg"): "JSM215b",
    ("Ostkustbanan", "Gävle-Kringlan"): "XSM300c",
    ("Ostkustbanan", "Kringlan-Dingersjö"): None,  # mellanetapp utan eget planobjekt
    ("Ostkustbanan", "Kubikenborg-Sundsvall C"): "JSM215",
    ("Ostlänken", "Järna-Linköping"): "JO1811",
    ("Sydostlänken", "Olofström-Sandbäck"): "JSY202",
    ("Västkustbanan", "Varberg, tunnel"): "BVGB015",
    ("Västlänken", "Göteborg, tunnel"): "VVA119",  # finansieras via Västsvenska paketet
    ("Ådalsbanan", "Sundsvall - Härnösand"): None,  # framtida dubbelspår, ej i planen
    # Järnväg, framtida (lager 23)
    ("Bergslagsbanan", "Gävle-Forsbacka"): None,
    ("Ny stambana", "Göteborg-Borås"): "JVA200d",
    # Väg, planerad (lager 32)
    ("40 förbi Eksjö", ""): "VSO033",
    ("50 Nykyrka-Brattebo backe", "Nykyrka-Brattebo backe"): "VMN096",
    ("55, Dunker-Björndammen", ""): None,
    ("55, förbi Flen", ""): None,
    ("56 Hedesunda-Gävle", ""): None,
    ("E14 Lockne-Optand", "Förbi Brunflo"): None,
    ("E18 Tpl Hjulsta", ""): None,  # trolig del av VST001d men ej säkerställd
    ("E20 Götene-Mariestad", ""): "VVA015",
    ("E22 Verkebäck-Gladhammar", ""): None,
    ("E22 förbi Bergkvara", ""): "YSY004",
    ("E22 förbi Söderköping", ""): "VSO004",
    ("E4 Förbifart Örnsköldsvik", ""): None,
    ("E4 Kongberget-Gnarp", ""): "VM034",
    ("E4 förbi Skellefteå", ""): "VN1801",
    ("E45 Rengsjön-Älvros", ""): "VM051",
    ("E45 Vattnäs-Trunna", ""): "VM001",
    ("E65 Svedala-Börringe", ""): "VSK050",
    ("Förbifart Stockholm", ""): "VST001",
    ("Tvärförbindelse Södertörn", ""): "VST005",
    ("Umeåprojektet, Västra länken", ""): None,  # öppnad 2021
    # Väg, framtida (lager 33)
    ("Östlig förbindelse", ""): "VOR2606",  # endast utredning i planen
}

# Planobjekt vars kostnadsram inte avser korridorens projekt specifikt
# (paketfinansiering respektive enbart utredningsmedel) — budgeten
# utelämnas hellre än att vilseleda.
KOSTNAD_EJ_OBJEKTSPECIFIK = frozenset({"VVA119", "VOR2606"})

# Korridorer vars anläggning redan är öppnad för trafik men vars
# riksintresseanspråk ligger kvar i tjänstens planerad-lager. Utan detta
# skulle None-kopplingen visa en färdigbyggd anläggning som en kommande
# investering (derive_status(None) → planerad).
REDAN_OPPNADE = frozenset(
    {
        ("Godsstråket genom Bergslagen", "Jakobshyttan-Degerön"),  # dubbelspår öppnat 2023
        ("Umeåprojektet, Västra länken", ""),  # öppnad 2021
    }
)

# Bilaga 1:s fasindelning → projektstatus. "Byggstart" och "Förberedelse
# för byggstart" är beviljade byggstartsgrupper, inte påbörjade byggen —
# de förblir planerade tills planen listar dem som pågående.
FAS_TILL_STATUS = {
    "Pågående": ProjectStatus.PAGAENDE,
    "Öppet för trafik": ProjectStatus.AVSLUTAD,
}


@cache
def bilaga1_objekt() -> dict[str, dict[str, Any]]:
    """Läs den genererade attributtabellen ur Bilaga 1 (objekt-id → attribut)."""
    try:
        return loads(BILAGA1_PATH.read_text(encoding="utf-8"))
    except (OSError, JSONDecodeError) as exc:
        raise DataSourceError(
            "nationell_plan",
            f"Kunde inte läsa {BILAGA1_PATH.name} — kör scripts/import_bilaga1.py: {exc}",
        ) from exc


def slugify(text: str) -> str:
    """ASCII-slug för externa id:n: gemener, åäö översatta, bindestreck."""
    text = text.strip().lower()
    for src, dst in (("å", "a"), ("ä", "a"), ("ö", "o"), ("é", "e")):
        text = text.replace(src, dst)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def derive_status(fas: str | None) -> ProjectStatus:
    """Härled status ur Bilaga 1:s fasindelning; utan fas är korridoren planerad."""
    if fas is None:
        return ProjectStatus.PLANERAD
    return FAS_TILL_STATUS.get(fas, ProjectStatus.PLANERAD)


def _ytdelar(geom: shapely.Geometry) -> shapely.Geometry | None:
    """Behåll geometrins ytdelar. make_valid och set_precision kan lämna
    linje-/punktrester efter degenererade polygoner (spikar, kollinjära
    ringar) — kontraktet mot kartlagren är (Multi)Polygon."""
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    if geom.geom_type == "GeometryCollection":
        ytor = [g for g in geom.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
        if ytor:
            return shapely.union_all(ytor)
    return None


def assemble_geometry(parts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Slå ihop en grupps delytor till en sammanhängande (Multi)Polygon.

    Korridorerna levereras styckade i upp till tusentals små delytor
    (Norrbotniabanan: ~1100). Unionen löser upp inre delningskanter och
    koordinaterna snappas till 6 decimaler (~0,1 m) — annars blir en
    enda korridor flera MB GeoJSON i varje API-svar.
    """
    geoms = []
    for part in parts:
        if not part or part.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        try:
            geom = shape(part)
            if not geom.is_valid:
                geom = shapely.make_valid(geom)
        # Samma breda uppsättning som geo.py — shape() kastar KeyError/
        # TypeError/AttributeError på missbildad GeoJSON, inte bara
        # ShapelyError.
        except (ShapelyError, ValueError, KeyError, TypeError, AttributeError):
            logger.warning("Hoppar över otolkbar delyta i riksintressedata")
            continue
        geom = _ytdelar(geom)
        if geom is not None:
            geoms.append(geom)
    if not geoms:
        return None

    merged = shapely.set_precision(shapely.union_all(geoms), 1e-6)
    if merged.is_empty:
        return None
    merged = _ytdelar(merged)
    if merged is None or merged.is_empty:
        return None
    return mapping(merged)


def _geometry_in_bbox(geometry: dict[str, Any], bbox: Bbox) -> bool:
    """Skyddsnät utöver tjänstens spatiala filter (samma mönster som
    Trafikverket-källan)."""
    try:
        geom = shape(geometry)
    except (ShapelyError, ValueError):
        return False
    west, south, east, north = bbox
    return shapely.box(west, south, east, north).intersects(geom)


def build_query_params(offset: int, bbox: Bbox | None = None) -> dict[str, str]:
    """Frågeparametrar för ett ArcGIS-lager: GeoJSON i WGS84, stabil
    paginering via objectid-sortering."""
    params = {
        "where": "1=1",
        "outFields": "*",
        "orderByFields": "objectid",
        "resultOffset": str(offset),
        "resultRecordCount": str(REQUEST_LIMIT),
        "f": "geojson",
    }
    if bbox is not None:
        west, south, east, north = bbox
        params.update(
            {
                "geometry": f"{west},{south},{east},{north}",
                "geometryType": "esriGeometryEnvelope",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
            }
        )
    return params


@register
class NationellPlanDataSource(DataSource):
    name = "nationell_plan"
    display_name = "Trafikverket (nationell plan)"

    def __init__(self, service_url: str | None = None) -> None:
        # Sätts i tester; annars löses adressen upp vid varje hämtning.
        self._service_url = service_url
        self.truncated = False

    async def fetch_infrastructure_projects(
        self, bbox: Bbox | None = None
    ) -> list[InfrastructureProjectIngest]:
        self.truncated = False
        per_id: dict[str, InfrastructureProjectIngest] = {}

        async with httpx.AsyncClient(timeout=60.0) as client:
            service_url = self._service_url or await self._resolve_service_url(client)
            for lager in LAGER:
                features = await self._fetch_layer(client, service_url, lager.lager_id, bbox)
                for ingest in self._build_projects(lager, features, bbox):
                    # Skulle samma korridor ligga i både planerad- och
                    # framtida-lagret har planerad företräde (mognare
                    # uppgift) — id:t är avsiktligt tidsperspektivlöst.
                    befintlig = per_id.get(ingest.external_id)
                    if befintlig and befintlig.metadata_json["tidsperspektiv"] == "planerad":
                        continue
                    per_id[ingest.external_id] = ingest

        results = list(per_id.values())
        logger.info("Hämtade %d investeringsprojekt ur nationell plan", len(results))
        return results

    async def _resolve_service_url(self, client: httpx.AsyncClient) -> str:
        """Följ WMS-ingångens redirect till den aktuella versionerade tjänsten.

        Misslyckad upplösning är inte ett hämtningsfel — reservadressen
        används och ett riktigt fel uppstår först om även den är död.
        """
        try:
            response = await client.get(REDIRECT_URL, follow_redirects=False)
            match = _SERVICE_PATH_RE.match(response.headers.get("location", ""))
            if match:
                host, service_path = match.groups()
                return f"https://{host}/gis/rest/services/{service_path}"
            logger.warning(
                "Riksintressetjänstens redirect kunde inte tolkas — använder senast kända adress"
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "Kunde inte lösa upp riksintressetjänstens adress (%s) — använder senast kända",
                exc,
            )
        return DEFAULT_SERVICE_URL

    async def _fetch_layer(
        self,
        client: httpx.AsyncClient,
        service_url: str,
        lager_id: int,
        bbox: Bbox | None,
    ) -> list[dict[str, Any]]:
        """Hämta ett lagers samtliga features med paginering.

        En kort sida betyder inte sista sidan: ArcGIS klampar tyst
        resultRecordCount till tjänstens maxRecordCount (som kan vara
        lägre än REQUEST_LIMIT i en framtida tjänstversion) och
        signalerar fortsättning med exceededTransferLimit. Flaggan styr;
        full sida är reserv om den skulle saknas.
        """
        features: list[dict[str, Any]] = []
        offset = 0
        for _ in range(MAX_PAGES):
            data = await self._request(client, service_url, lager_id, offset, bbox)
            page_features = data.get("features") or []
            features.extend(f for f in page_features if isinstance(f, dict))
            offset += len(page_features)
            exceeded = bool(
                data.get("exceededTransferLimit")
                or (data.get("properties") or {}).get("exceededTransferLimit")
            )
            if not page_features or not (exceeded or len(page_features) >= REQUEST_LIMIT):
                break
        else:
            logger.warning(
                "Nationell plan: sidgränsen (%d sidor) nådd för lager %d — trunkerad hämtning",
                MAX_PAGES,
                lager_id,
            )
            self.truncated = True
        return features

    async def _request(
        self,
        client: httpx.AsyncClient,
        service_url: str,
        lager_id: int,
        offset: int,
        bbox: Bbox | None,
    ) -> dict[str, Any]:
        try:
            response = await client.get(
                f"{service_url}/{lager_id}/query", params=build_query_params(offset, bbox)
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DataSourceError(self.name, f"API-anropet misslyckades: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise DataSourceError(self.name, "Svaret kunde inte tolkas som JSON") from exc

        # ArcGIS rapporterar fel som HTTP 200 med ett error-objekt i kroppen.
        if not isinstance(data, dict) or "error" in data:
            detail = data.get("error") if isinstance(data, dict) else data
            raise DataSourceError(self.name, f"Tjänsten svarade med fel: {detail}")
        return data

    def _build_projects(
        self, lager: Lager, features: list[dict[str, Any]], bbox: Bbox | None
    ) -> list[InfrastructureProjectIngest]:
        """Gruppera lagrets delytor per projekt och bygg ingest-objekt."""
        grupper: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for feature in features:
            props = feature.get("properties") or {}
            gen = (props.get("GenNamn") or "").strip()
            if not gen:
                logger.warning(
                    "Hoppar över riksintresseyta utan GenNamn (lager %d)", lager.lager_id
                )
                continue
            spec = (props.get("SpecNamn") or "").strip()
            grupper.setdefault((gen, spec), []).append(feature)

        results = []
        for (gen, spec), parts in sorted(grupper.items()):
            ingest = self._build_ingest(lager, gen, spec, parts)
            if ingest is None:
                continue
            if bbox and ingest.geometry and not _geometry_in_bbox(ingest.geometry, bbox):
                continue
            results.append(ingest)
        return results

    def _build_ingest(
        self, lager: Lager, gen: str, spec: str, parts: list[dict[str, Any]]
    ) -> InfrastructureProjectIngest | None:
        geometry = assemble_geometry([p.get("geometry") for p in parts])
        if geometry is None:
            # Utan korridor finns inget att visa på kartan — hoppa över
            # med varning i stället för att skapa ett osynligt projekt.
            logger.warning("Hoppar över %s (%s): ingen tolkbar geometri", gen, spec or "—")
            return None

        props = parts[0].get("properties") or {}
        objekt_id = BILAGA1_KOPPLING.get((gen, spec))
        objekt = bilaga1_objekt().get(objekt_id) if objekt_id else None
        if objekt_id and objekt is None:
            logger.warning(
                "Kopplingen (%s, %s) pekar på %s som saknas i Bilaga 1-tabellen",
                gen,
                spec,
                objekt_id,
            )

        budget_sek = None
        if objekt and objekt_id not in KOSTNAD_EJ_OBJEKTSPECIFIK and objekt.get("kostnad_mnkr"):
            budget_sek = int(objekt["kostnad_mnkr"]) * 1_000_000

        metadata: dict[str, Any] = {
            "lan": props.get("Län"),
            "region": props.get("Region"),
            "riksintresse_status": props.get("Status"),
            "tidsperspektiv": lager.tidsperspektiv,
            "identifieringskod": props.get("Identifieringskod"),
            "antal_delytor": len(parts),
            "lank": props.get("Lank"),
        }
        if objekt:
            metadata.update(
                {
                    "bilaga1_objekt_id": objekt_id,
                    "bilaga1_namn": objekt.get("namn"),
                    "bilaga1_fas": objekt.get("fas"),
                }
            )

        # Tidsperspektivet ingår avsiktligt INTE i id:t — en korridor som
        # flyttas från framtida- till planerad-lagret vid ett nytt
        # riksintressebeslut ska behålla sin identitet i upserten, inte
        # lämna kvar en dubblettrad under det gamla id:t.
        external_id = f"ntp:{slugify(lager.projekttyp.value)}:{slugify(gen)}"
        if spec:
            external_id += f":{slugify(spec)}"

        if (gen, spec) in REDAN_OPPNADE:
            status = ProjectStatus.AVSLUTAD
        else:
            status = derive_status(objekt.get("fas") if objekt else None)

        return InfrastructureProjectIngest(
            external_id=external_id,
            source=self.name,
            name=f"{gen} ({spec})" if spec else gen,
            description=(props.get("AtgBeskr") or props.get("GenBeskr") or "").strip() or None,
            project_type=lager.projekttyp,
            status=status,
            budget_sek=budget_sek,
            geometry=geometry,
            impact_radius_m=IMPACT_RADIUS_M[lager.projekttyp],
            metadata_json=metadata,
        )
