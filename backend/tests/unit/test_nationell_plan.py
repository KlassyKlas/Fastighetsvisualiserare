"""Enhetstester för nationell plan-källan — gruppering, berikning och fel."""

import httpx
import pytest
import respx

from app.datasources.base import DataSourceError
from app.datasources.nationell_plan import (
    DEFAULT_SERVICE_URL,
    LAGER,
    REDIRECT_URL,
    NationellPlanDataSource,
    assemble_geometry,
    bilaga1_objekt,
    build_query_params,
    derive_status,
    slugify,
)
from app.domain import ProjectStatus, ProjectType

SERVICE = "https://example.trafikverket.se/gis/rest/services/Riksintressen/Test/MapServer"


def _square(lng: float, lat: float, size: float = 0.01) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [lng, lat],
                [lng + size, lat],
                [lng + size, lat + size],
                [lng, lat + size],
                [lng, lat],
            ]
        ],
    }


def _feature(
    gen: str,
    spec: str | None = None,
    geometry: dict | None = None,
    **props,
) -> dict:
    return {
        "type": "Feature",
        "geometry": geometry if geometry is not None else _square(16.0, 58.6),
        "properties": {
            "GenNamn": gen,
            "SpecNamn": spec,
            "Län": "Östergötland",
            "Region": "Öst",
            "Status": "Planerad",
            "AtgBeskr": "Ny järnväg.",
            "Identifieringskod": "RI_Ko_Jb_p_0001",
            **props,
        },
    }


def _collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


class TestSlugify:
    def test_svenska_tecken_och_skiljetecken(self):
        assert slugify("Ostlänken") == "ostlanken"
        assert slugify("Järna-Linköping") == "jarna-linkoping"
        assert slugify("Västlänken, Göteborg") == "vastlanken-goteborg"

    def test_yttre_blanksteg_trimmas(self):
        assert slugify("  Byarum - Tenhult  ") == "byarum-tenhult"


class TestDeriveStatus:
    def test_pagaende_och_avslutad(self):
        assert derive_status("Pågående") == ProjectStatus.PAGAENDE
        assert derive_status("Öppet för trafik") == ProjectStatus.AVSLUTAD

    def test_byggstart_ar_fortfarande_planerad(self):
        # Byggstartsgrupperna är beviljade, inte påbörjade byggen
        assert derive_status("Byggstart") == ProjectStatus.PLANERAD
        assert derive_status("Förberedelse för byggstart") == ProjectStatus.PLANERAD

    def test_okand_eller_saknad_fas_ar_planerad(self):
        assert derive_status("Planering") == ProjectStatus.PLANERAD
        assert derive_status(None) == ProjectStatus.PLANERAD


class TestAssembleGeometry:
    def test_angransande_delytor_unioneras_utan_inre_kanter(self):
        # Två rutor som delar en kant ska bli EN polygon, inte en
        # multipolygon med delningskant kvar
        result = assemble_geometry([_square(16.0, 58.6), _square(16.01, 58.6)])
        assert result["type"] == "Polygon"

    def test_separata_delytor_blir_multipolygon(self):
        result = assemble_geometry([_square(16.0, 58.6), _square(17.0, 59.6)])
        assert result["type"] == "MultiPolygon"
        assert len(result["coordinates"]) == 2

    def test_koordinater_snappas_till_6_decimaler(self):
        result = assemble_geometry([_square(16.123456789, 58.6)])
        lngs = {round(point[0], 6) for point in result["coordinates"][0]}
        assert all(abs(point[0] - round(point[0], 6)) < 1e-12 for point in result["coordinates"][0])
        assert 16.123457 in lngs

    def test_otolkbara_delytor_hoppas_over(self):
        result = assemble_geometry([None, {"type": "Point", "coordinates": [16, 58]}])
        assert result is None

    def test_missbildad_geojson_kraschar_inte(self):
        # shape() kastar KeyError/TypeError på missbildad GeoJSON — en
        # trasig delyta får inte fälla hela synken med HTTP 500
        missbildade = [
            {"type": "Polygon"},  # coordinates saknas → KeyError
            {"type": "MultiPolygon", "coordinates": [[[1, 2]]]},  # fel nästling → TypeError
        ]
        assert assemble_geometry(missbildade) is None
        # ...och en giltig delyta bredvid en trasig överlever
        result = assemble_geometry([*missbildade, _square(16.0, 58.6)])
        assert result["type"] == "Polygon"

    def test_degenererad_polygon_ger_inte_linjerester(self):
        # Kollinjär ring: make_valid ger en LineString — kontraktet mot
        # kartlagren är (Multi)Polygon, aldrig GeometryCollection/linjer
        kollinjar = {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [2, 2], [0, 0]]]}
        assert assemble_geometry([kollinjar]) is None
        result = assemble_geometry([kollinjar, _square(16.0, 58.6)])
        assert result["type"] == "Polygon"

    def test_tom_lista_ger_none(self):
        assert assemble_geometry([]) is None


class TestBuildQueryParams:
    def test_geojson_och_paginering(self):
        params = build_query_params(offset=4000)
        assert params["f"] == "geojson"
        assert params["resultOffset"] == "4000"
        assert params["orderByFields"] == "objectid"

    def test_bbox_ger_envelope_filter(self):
        params = build_query_params(0, bbox=(16.0, 58.0, 17.0, 59.0))
        assert params["geometry"] == "16.0,58.0,17.0,59.0"
        assert params["geometryType"] == "esriGeometryEnvelope"
        assert params["inSR"] == "4326"


class TestBuildProjects:
    def setup_method(self):
        self.source = NationellPlanDataSource(service_url=SERVICE)
        self.lager_jarnvag = LAGER[0]  # 22, järnväg, planerad

    def test_delytor_grupperas_per_namn(self):
        features = [
            _feature("Ostlänken", "Järna-Linköping", _square(16.0, 58.6)),
            _feature("Ostlänken", "Järna-Linköping", _square(16.01, 58.6)),
            _feature("Alvesta triangelspår", None, _square(14.5, 56.9)),
        ]
        results = self.source._build_projects(self.lager_jarnvag, features, bbox=None)
        assert [r.external_id for r in results] == [
            "ntp:jarnvag:alvesta-triangelspar",
            "ntp:jarnvag:ostlanken:jarna-linkoping",
        ]
        ostlanken = results[1]
        assert ostlanken.name == "Ostlänken (Järna-Linköping)"
        assert ostlanken.metadata_json["antal_delytor"] == 2

    def test_namn_med_yttre_blanksteg_matchar_kopplingen(self):
        # Riksintressedatat har efterhängande blanksteg i flera namn
        features = [_feature("Sydostlänken  ", "Olofström-Sandbäck ")]
        results = self.source._build_projects(self.lager_jarnvag, features, bbox=None)
        assert results[0].metadata_json["bilaga1_objekt_id"] == "JSY202"

    def test_bilaga1_berikning_ger_budget_och_status(self):
        features = [_feature("Ostlänken", "Järna-Linköping")]
        results = self.source._build_projects(self.lager_jarnvag, features, bbox=None)
        ostlanken = results[0]
        forvantad = bilaga1_objekt()["JO1811"]["kostnad_mnkr"] * 1_000_000
        assert ostlanken.budget_sek == forvantad
        assert ostlanken.status == ProjectStatus.PAGAENDE  # fas "Pågående" i Bilaga 1
        assert ostlanken.metadata_json["bilaga1_namn"].startswith("Ostlänken")

    def test_paketfinansierad_kostnad_utelamnas(self):
        # Västlänken finansieras via Västsvenska paketet — paketets ram
        # får inte redovisas som projektets budget
        features = [_feature("Västlänken", "Göteborg, tunnel")]
        results = self.source._build_projects(self.lager_jarnvag, features, bbox=None)
        assert results[0].budget_sek is None
        assert results[0].status == ProjectStatus.PAGAENDE
        assert results[0].metadata_json["bilaga1_objekt_id"] == "VVA119"

    def test_okopplad_korridor_far_ingen_berikning(self):
        features = [_feature("Helt ny korridor", "Testetapp")]
        results = self.source._build_projects(self.lager_jarnvag, features, bbox=None)
        okand = results[0]
        assert okand.budget_sek is None
        assert okand.status == ProjectStatus.PLANERAD
        assert "bilaga1_objekt_id" not in okand.metadata_json

    def test_vaglager_ger_vagtyp_och_radie(self):
        lager_vag = LAGER[2]  # 32, väg, planerad
        features = [_feature("Förbifart Stockholm", None, _square(17.8, 59.3))]
        results = self.source._build_projects(lager_vag, features, bbox=None)
        forbifarten = results[0]
        assert forbifarten.project_type == ProjectType.VAG
        assert forbifarten.impact_radius_m == 2000.0
        # Tidsperspektivet ingår inte i id:t — identiteten ska överleva
        # en flytt mellan planerad- och framtida-lagren
        assert forbifarten.external_id == "ntp:vag:forbifart-stockholm"
        assert forbifarten.status == ProjectStatus.PAGAENDE  # VST001 pågår

    def test_redan_oppnad_anlaggning_blir_avslutad(self):
        # Västra länken öppnade 2021 men korridoren ligger kvar i
        # planerad-lagret — får inte visas som kommande investering
        lager_vag = LAGER[2]
        features = [_feature("Umeåprojektet, Västra länken", None, _square(20.2, 63.8))]
        results = self.source._build_projects(lager_vag, features, bbox=None)
        assert results[0].status == ProjectStatus.AVSLUTAD

    def test_grupp_utan_geometri_hoppas_over(self):
        features = [_feature("Ostlänken", "Järna-Linköping", geometry=None)]
        features[0]["geometry"] = None
        assert self.source._build_projects(self.lager_jarnvag, features, bbox=None) == []

    def test_feature_utan_gennamn_hoppas_over(self):
        features = [_feature("", None)]
        assert self.source._build_projects(self.lager_jarnvag, features, bbox=None) == []

    def test_bbox_skyddsnat_filtrerar(self):
        features = [_feature("Ostlänken", "Järna-Linköping", _square(16.0, 58.6))]
        norrland = (19.0, 64.0, 22.0, 66.0)
        assert self.source._build_projects(self.lager_jarnvag, features, bbox=norrland) == []


def _mock_layers(per_layer: dict[int, list[dict]], *, exclude: set[int] = frozenset()) -> None:
    for lager in LAGER:
        if lager.lager_id in exclude:
            continue
        respx.get(f"{SERVICE}/{lager.lager_id}/query").mock(
            return_value=httpx.Response(200, json=_collection(per_layer.get(lager.lager_id, [])))
        )


class TestFetch:
    @respx.mock
    async def test_happy_path(self):
        _mock_layers({22: [_feature("Ostlänken", "Järna-Linköping")]})
        source = NationellPlanDataSource(service_url=SERVICE)
        results = await source.fetch_infrastructure_projects()
        assert len(results) == 1
        assert results[0].source == "nationell_plan"
        assert source.truncated is False

    @respx.mock
    async def test_http_fel_kastas_vidare(self):
        respx.get(f"{SERVICE}/22/query").mock(return_value=httpx.Response(500))
        source = NationellPlanDataSource(service_url=SERVICE)
        with pytest.raises(DataSourceError, match="misslyckades"):
            await source.fetch_infrastructure_projects()

    @respx.mock
    async def test_arcgis_fel_i_200_svar_kastas(self):
        # ArcGIS rapporterar fel som HTTP 200 med error-objekt i kroppen
        respx.get(f"{SERVICE}/22/query").mock(
            return_value=httpx.Response(
                200, json={"error": {"code": 400, "message": "Invalid layer"}}
            )
        )
        source = NationellPlanDataSource(service_url=SERVICE)
        with pytest.raises(DataSourceError, match="Invalid layer"):
            await source.fetch_infrastructure_projects()

    @respx.mock
    async def test_ogiltig_json_kastas(self):
        respx.get(f"{SERVICE}/22/query").mock(
            return_value=httpx.Response(200, text="<html>fel</html>")
        )
        source = NationellPlanDataSource(service_url=SERVICE)
        with pytest.raises(DataSourceError, match="JSON"):
            await source.fetch_infrastructure_projects()


class TestPagination:
    @respx.mock
    async def test_full_sida_ger_foljdfraga(self, monkeypatch):
        import app.datasources.nationell_plan as np_modul

        monkeypatch.setattr(np_modul, "REQUEST_LIMIT", 1)
        respx.get(f"{SERVICE}/22/query").mock(
            side_effect=[
                httpx.Response(200, json=_collection([_feature("Ostlänken", "Järna-Linköping")])),
                httpx.Response(
                    200,
                    json=_collection([_feature("Alvesta triangelspår", None, _square(14.5, 56.9))]),
                ),
                httpx.Response(200, json=_collection([])),
            ]
        )
        _mock_layers({}, exclude={22})  # 23/32/33 tomma
        source = NationellPlanDataSource(service_url=SERVICE)
        results = await source.fetch_infrastructure_projects()
        assert len(results) == 2
        assert source.truncated is False

    @respx.mock
    async def test_kort_sida_med_exceeded_flagga_fortsatter(self):
        # ArcGIS klampar resultRecordCount tyst till tjänstens
        # maxRecordCount: en kort sida med exceededTransferLimit=true
        # betyder "det finns mer" — inte sista sidan
        sida1 = _collection([_feature("Ostlänken", "Järna-Linköping")])
        sida1["exceededTransferLimit"] = True
        sida2 = _collection([_feature("Alvesta triangelspår", None, _square(14.5, 56.9))])
        respx.get(f"{SERVICE}/22/query").mock(
            side_effect=[httpx.Response(200, json=sida1), httpx.Response(200, json=sida2)]
        )
        _mock_layers({}, exclude={22})
        source = NationellPlanDataSource(service_url=SERVICE)
        results = await source.fetch_infrastructure_projects()
        assert len(results) == 2
        assert source.truncated is False

    @respx.mock
    async def test_dedupe_over_lager_planerad_vinner(self):
        # Samma korridor i både planerad- och framtida-lagret får inte
        # bli två rader — planerad har företräde
        _mock_layers(
            {
                22: [_feature("Ostlänken", "Järna-Linköping")],
                23: [_feature("Ostlänken", "Järna-Linköping", _square(16.5, 58.8))],
            }
        )
        source = NationellPlanDataSource(service_url=SERVICE)
        results = await source.fetch_infrastructure_projects()
        assert len(results) == 1
        assert results[0].metadata_json["tidsperspektiv"] == "planerad"

    @respx.mock
    async def test_sidgransen_flaggar_trunkering(self, monkeypatch):
        import app.datasources.nationell_plan as np_modul

        monkeypatch.setattr(np_modul, "REQUEST_LIMIT", 1)
        monkeypatch.setattr(np_modul, "MAX_PAGES", 2)
        respx.get(f"{SERVICE}/22/query").mock(
            return_value=httpx.Response(
                200, json=_collection([_feature("Ostlänken", "Järna-Linköping")])
            )
        )
        _mock_layers({}, exclude={22})
        source = NationellPlanDataSource(service_url=SERVICE)
        await source.fetch_infrastructure_projects()
        assert source.truncated is True


class TestResolveServiceUrl:
    @respx.mock
    async def test_redirect_ger_aktuell_adress(self):
        respx.get(REDIRECT_URL).mock(
            return_value=httpx.Response(
                302,
                headers={
                    "location": (
                        "https://ny-host.trafikverket.se/gis/services/"
                        "Riksintressen/Riksintressen_Prod_2027_01/MapServer/WMSServer?"
                    )
                },
            )
        )
        for lager in LAGER:
            respx.get(
                "https://ny-host.trafikverket.se/gis/rest/services/"
                f"Riksintressen/Riksintressen_Prod_2027_01/MapServer/{lager.lager_id}/query"
            ).mock(return_value=httpx.Response(200, json=_collection([])))

        source = NationellPlanDataSource()
        results = await source.fetch_infrastructure_projects()
        assert results == []

    @respx.mock
    async def test_obegriplig_redirect_faller_tillbaka(self):
        respx.get(REDIRECT_URL).mock(return_value=httpx.Response(200, text="ingen redirect"))
        for lager in LAGER:
            respx.get(f"{DEFAULT_SERVICE_URL}/{lager.lager_id}/query").mock(
                return_value=httpx.Response(200, json=_collection([]))
            )
        source = NationellPlanDataSource()
        assert await source.fetch_infrastructure_projects() == []


class TestRegistrering:
    def test_kallan_ar_registrerad(self):
        from app.datasources import available_sources

        sources = available_sources()
        assert sources["nationell_plan"] == "Trafikverket (nationell plan)"
