"""Fixturerna valideras redan av sina ingest-modeller vid import —
dessa tester kontrollerar det som modellerna inte kan uttrycka."""

from shapely.geometry import shape

from app.seed_data import INFRASTRUCTURE_PROJECTS, PROPERTIES


def test_external_ids_unique():
    ids = [p.external_id for p in INFRASTRUCTURE_PROJECTS]
    assert len(ids) == len(set(ids))


def test_designations_unique():
    designations = [p.designation for p in PROPERTIES]
    assert len(designations) == len(set(designations))


def test_all_geometries_valid_and_in_sweden():
    for item in [*INFRASTRUCTURE_PROJECTS, *PROPERTIES]:
        assert item.geometry is not None
        geom = shape(item.geometry)
        assert geom.is_valid
        # Sveriges ungefärliga utbredning i WGS84
        minx, miny, maxx, maxy = geom.bounds
        assert 10 <= minx <= maxx <= 25
        assert 55 <= miny <= maxy <= 70


def test_sample_export_matches_schemas():
    from scripts.export_sample_data import build_sample_data

    data = build_sample_data()
    assert data["properties"]["numberReturned"] == len(PROPERTIES)
    assert data["infrastructureProjects"]["numberReturned"] == len(INFRASTRUCTURE_PROJECTS)
    # Zoner ska finnas även för linjeprojekt — inte bara punkter
    zone_types = {f["geometry"]["type"] for f in data["impactZones"]["features"]}
    assert zone_types <= {"Polygon", "MultiPolygon"}
    assert len(data["impactZones"]["features"]) == len(INFRASTRUCTURE_PROJECTS)
