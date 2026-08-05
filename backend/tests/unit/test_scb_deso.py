"""Enhetstester för SCB DeSO-källan — json-stat2, vintage-suffix och fel."""

import pytest
import respx

from app.datasources.base import DataSourceError
from app.datasources.scb_deso import (
    DESO2025_SUFFIX,
    ScbDesoDataSource,
    _json_stat2_values,
)

WFS = "https://example.scb.se/geoserver/stat/ows"
PXWEB = "https://example.scb.se/pxweb"
POP = f"{PXWEB}/BE/BE0101/BE0101Y/FolkmDesoAldKon"
INC = f"{PXWEB}/HE/HE0110/HE0110I/Tab2InkDesoRegso"
EDU = f"{PXWEB}/UF/UF0506/UF0506D/UtbSUNBefDesoRegsoN"


def _square(lng: float, lat: float, size: float = 0.05) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [[lng, lat], [lng + size, lat], [lng + size, lat + size], [lng, lat], [lng, lat]]
        ],
    }


def _wfs_feature(deso_code: str, lng: float = 18.0, lat: float = 59.3) -> dict:
    return {
        "type": "Feature",
        "geometry": _square(lng, lat),
        "properties": {
            "desokod": deso_code,
            "kommunkod": deso_code[:4],
            "lanskod": deso_code[:2],
            "regsokod": f"{deso_code[:4]}R001",
        },
    }


def _wfs_page(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def _metadata(latest_year: str, extra_variables: list[dict] | None = None) -> dict:
    return {
        "variables": [
            {
                "code": "Region",
                "values": ["0180", "0180C1010" + DESO2025_SUFFIX],
                "valueTexts": ["0180 Stockholm", "0180C1010"],
            },
            *(extra_variables or []),
            {"code": "Tid", "values": ["2023", latest_year], "valueTexts": ["2023", latest_year]},
        ]
    }


def _json_stat2(region_codes: list[str], values: list, extra_dims: dict | None = None) -> dict:
    """Minimalt json-stat2-svar: Region först, ev. extra dimension efter."""
    ids = ["Region"]
    sizes = [len(region_codes)]
    dimension = {
        "Region": {"category": {"index": {code: i for i, code in enumerate(region_codes)}}}
    }
    for name, categories in (extra_dims or {}).items():
        ids.append(name)
        sizes.append(len(categories))
        dimension[name] = {"category": {"index": {c: i for i, c in enumerate(categories)}}}
    return {"id": ids, "size": sizes, "dimension": dimension, "value": values}


class TestJsonStat2Values:
    def test_endimensionellt_svar(self):
        data = _json_stat2(["a", "b"], [10, 20])
        assert _json_stat2_values(data) == {"a": [10], "b": [20]}

    def test_block_per_region_med_efterfoljande_dimension(self):
        data = _json_stat2(["a", "b"], [1, 2, 3, 4], extra_dims={"Niva": ["x", "y"]})
        assert _json_stat2_values(data) == {"a": [1, 2], "b": [3, 4]}

    def test_region_maste_vara_forst(self):
        data = _json_stat2(["a"], [1, 2], extra_dims={"Niva": ["x", "y"]})
        data["id"] = ["Niva", "Region"]
        data["size"] = [2, 1]
        with pytest.raises(DataSourceError):
            _json_stat2_values(data)


def _mock_happy_path(deso_codes: list[str]) -> None:
    respx.get(WFS).respond(json=_wfs_page([_wfs_feature(c) for c in deso_codes]))

    suffixed = [c + DESO2025_SUFFIX for c in deso_codes]

    respx.get(POP).respond(json=_metadata("2025"))
    respx.post(POP).respond(json=_json_stat2(suffixed, [1500 + i for i in range(len(suffixed))]))

    respx.get(INC).respond(json=_metadata("2024"))
    respx.post(INC).respond(json=_json_stat2(suffixed, [450.5] * len(suffixed)))

    respx.get(EDU).respond(json=_metadata("2025"))
    niva = ["21", "3+4", "5", "6", "US"]
    edu_values = []
    for _ in suffixed:
        edu_values.extend([100, 300, 200, 350, 50])  # egym = 550/1000
    respx.post(EDU).respond(
        json=_json_stat2(suffixed, edu_values, extra_dims={"UtbildningsNiva": niva})
    )


@respx.mock
async def test_bygger_ingest_med_statistik():
    _mock_happy_path(["0180C1010", "0182C1020"])
    source = ScbDesoDataSource(wfs_url=WFS, pxweb_base=PXWEB)

    areas = await source.fetch_deso_areas()

    assert len(areas) == 2
    area = areas[0]
    assert area.deso_code == "0180C1010"
    assert area.municipality_code == "0180"
    assert area.municipality == "Stockholm"  # kodprefixet strippat
    assert area.population == 1500
    assert area.population_year == 2025
    assert area.mean_income_sek == 450500  # tkr → kr
    assert area.stats_json["inkomstar"] == 2024
    assert area.geometry["type"] in ("Polygon", "MultiPolygon")


@respx.mock
async def test_utbildningsandel_beraknas_ur_nivablocken():
    _mock_happy_path(["0180C1010"])
    source = ScbDesoDataSource(wfs_url=WFS, pxweb_base=PXWEB)

    areas = await source.fetch_deso_areas()

    assert areas[0].higher_education_share == pytest.approx(0.55)


@respx.mock
async def test_bbox_filtrerar_klientledes():
    respx.get(WFS).respond(
        json=_wfs_page(
            [
                _wfs_feature("0180C1010", lng=18.0, lat=59.3),
                _wfs_feature("2480C1010", lng=20.2, lat=63.8),  # Umeå — utanför bbox
            ]
        )
    )
    suffixed = ["0180C1010" + DESO2025_SUFFIX]
    respx.get(POP).respond(json=_metadata("2025"))
    pop_route = respx.post(POP).respond(json=_json_stat2(suffixed, [1000]))
    respx.get(INC).respond(json=_metadata("2024"))
    respx.post(INC).respond(json=_json_stat2(suffixed, [400.0]))
    respx.get(EDU).respond(json=_metadata("2025"))
    respx.post(EDU).respond(
        json=_json_stat2(
            suffixed,
            [100, 300, 200, 350, 50],
            extra_dims={"UtbildningsNiva": ["21", "3+4", "5", "6", "US"]},
        )
    )
    source = ScbDesoDataSource(wfs_url=WFS, pxweb_base=PXWEB)

    areas = await source.fetch_deso_areas(bbox=(17.5, 59.0, 18.5, 59.6))

    assert [a.deso_code for a in areas] == ["0180C1010"]
    # Statistik ska bara begäras för områdena inom bbox
    import json

    body = json.loads(pop_route.calls[0].request.content)
    region_query = next(q for q in body["query"] if q["code"] == "Region")
    assert region_query["selection"]["values"] == suffixed


@respx.mock
async def test_wfs_fel_ger_datasourceerror():
    respx.get(WFS).respond(status_code=503)
    source = ScbDesoDataSource(wfs_url=WFS, pxweb_base=PXWEB)

    with pytest.raises(DataSourceError):
        await source.fetch_deso_areas()


@respx.mock
async def test_pxweb_fel_ger_datasourceerror():
    respx.get(WFS).respond(json=_wfs_page([_wfs_feature("0180C1010")]))
    respx.get(POP).respond(status_code=429)
    source = ScbDesoDataSource(wfs_url=WFS, pxweb_base=PXWEB)

    with pytest.raises(DataSourceError):
        await source.fetch_deso_areas()
