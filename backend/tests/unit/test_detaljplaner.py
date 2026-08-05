"""Enhetstester för detaljplanskällan — mappning, paginering och fel."""

from datetime import date

import httpx
import pytest
import respx

from app.datasources.base import DataSourceError
from app.datasources.detaljplaner import (
    PAGE_LIMIT,
    PROXY_SEARCH_URL,
    DetaljplanerDataSource,
    build_search_body,
)

SEARCH_URL = "https://example.lantmateriet.se/sok/search"


def _square(lng: float = 18.1, lat: float = 59.3, size: float = 0.01) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [[lng, lat], [lng + size, lat], [lng + size, lat + size], [lng, lat], [lng, lat]]
        ],
    }


def _plan_feature(feature_id: str, **detaljplan_props) -> dict:
    detaljplan = {
        "objektidentitet": feature_id,
        "beteckning": "DP 123",
        "namn": "Detaljplan för Testområdet",
        "status": "laga kraft",
        "typ": "detaljplan",
        "datumPaborjat": "2020-01-01",
        "datumLagakraft": "2023-05-10",
        **detaljplan_props,
    }
    return {
        "id": feature_id,
        "type": "Feature",
        "geometry": _square(),
        "properties": {
            "title": detaljplan["namn"],
            "providers": [{"name": "Nacka kommun", "roles": ["producer"], "kod": "0182"}],
            "feature": {"typ": "detaljplan"},
            "detaljplan": detaljplan,
        },
    }


def _bestammelse_feature(feature_id: str) -> dict:
    feature = _plan_feature(feature_id)
    feature["properties"]["feature"]["typ"] = "användningsbestämmelse"
    return feature


def _collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


class TestBuildSearchBody:
    def test_utan_bbox_ingen_bbox_i_kroppen(self):
        body = build_search_body(None, None)
        assert "bbox" not in body
        assert body["query"] == {"feature.typ": {"eq": "detaljplan"}}

    def test_med_bbox_och_cursor(self):
        body = build_search_body((17.0, 59.0, 18.0, 60.0), "abc-123")
        assert body["bbox"] == [17.0, 59.0, 18.0, 60.0]
        assert body["bbox-crs"].endswith("CRS84")
        assert body["afterId"] == "abc-123"


@respx.mock
async def test_mappar_planfeatures_till_ingest():
    respx.post(SEARCH_URL).respond(
        json=_collection([_plan_feature("aaa-111"), _bestammelse_feature("bbb-222")])
    )
    source = DetaljplanerDataSource(search_url=SEARCH_URL)

    plans = await source.fetch_detail_plans()

    assert len(plans) == 1  # bestämmelsen filtreras bort
    plan = plans[0]
    assert plan.external_id == "aaa-111"
    assert plan.source == "detaljplaner"
    assert plan.name == "Detaljplan för Testområdet"
    assert plan.plan_number == "DP 123"
    assert plan.status == "laga kraft"
    assert plan.municipality == "Nacka"  # " kommun" strippas
    assert plan.adopted_date == date(2023, 5, 10)
    assert plan.metadata_json["kommunkod"] == "0182"
    assert plan.geometry["type"] == "Polygon"
    assert source.truncated is False


@respx.mock
async def test_paginerar_med_afterid_tills_kort_sida():
    first_page = _collection([_plan_feature(f"id-{i}") for i in range(PAGE_LIMIT)])
    second_page = _collection([_plan_feature("id-sista")])
    route = respx.post(SEARCH_URL)
    route.side_effect = [
        httpx.Response(200, json=first_page),
        httpx.Response(200, json=second_page),
    ]
    source = DetaljplanerDataSource(search_url=SEARCH_URL)

    plans = await source.fetch_detail_plans()

    assert len(plans) == PAGE_LIMIT + 1
    assert route.call_count == 2
    import json

    second_body = json.loads(route.calls[1].request.content)
    assert second_body["afterId"] == f"id-{PAGE_LIMIT - 1}"


@respx.mock
async def test_saknad_geometri_och_id_hoppas_over():
    utan_geometri = _plan_feature("ccc-333")
    utan_geometri["geometry"] = None
    utan_id = _plan_feature("")
    utan_id["id"] = None
    utan_id["properties"]["detaljplan"]["objektidentitet"] = None
    respx.post(SEARCH_URL).respond(json=_collection([utan_geometri, utan_id]))
    source = DetaljplanerDataSource(search_url=SEARCH_URL)

    assert await source.fetch_detail_plans() == []


@respx.mock
async def test_http_fel_ger_datasourceerror():
    respx.post(SEARCH_URL).respond(status_code=500)
    source = DetaljplanerDataSource(search_url=SEARCH_URL)

    with pytest.raises(DataSourceError):
        await source.fetch_detail_plans()


@respx.mock
async def test_401_ger_vagledande_fel():
    respx.post(SEARCH_URL).respond(status_code=401)
    source = DetaljplanerDataSource(search_url=SEARCH_URL)

    with pytest.raises(DataSourceError, match="Geotorget"):
        await source.fetch_detail_plans()


@respx.mock
async def test_utan_nycklar_anvands_proxyn():
    route = respx.post(PROXY_SEARCH_URL).respond(json=_collection([]))
    source = DetaljplanerDataSource()

    plans = await source.fetch_detail_plans()

    assert plans == []
    assert route.called
    # httpx standard-UA blockeras av proxyn — appen ska identifiera sig
    assert route.calls[0].request.headers["User-Agent"].startswith("Fastighetsvisualiserare")
