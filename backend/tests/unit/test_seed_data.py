"""Fixturerna valideras redan av sina ingest-modeller vid import —
dessa tester kontrollerar det som modellerna inte kan uttrycka."""

from datetime import UTC, datetime, time

from shapely.geometry import shape

from app.seed_data import DETAIL_PLANS, INFRASTRUCTURE_PROJECTS, PROPERTIES


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


def test_sample_export_timestamps_precede_reference_date():
    """Demodatats stämplar är illustrativa men får inte ligga i framtiden
    relativt referensdatumet — en demo-bevakning som skapas "nu" skulle
    annars se exempelobjekten som händelser."""
    from scripts.export_sample_data import REFERENCE_DATE, build_sample_data

    data = build_sample_data()
    assert data["referenceDate"] == REFERENCE_DATE.isoformat()

    reference = datetime.combine(REFERENCE_DATE, time.min, tzinfo=UTC)
    collections = {
        "properties": len(PROPERTIES),
        "infrastructureProjects": len(INFRASTRUCTURE_PROJECTS),
        "detailPlans": len(DETAIL_PLANS),
    }
    for key, expected_count in collections.items():
        features = data[key]["features"]
        assert len(features) == expected_count
        for feature in features:
            props = feature["properties"]
            # Pydantic serialiserar UTC som "...Z" — samma form som API:t
            assert props["created_at"].endswith("Z")
            created = datetime.fromisoformat(props["created_at"])
            updated = datetime.fromisoformat(props["updated_at"])
            assert created <= updated < reference

    # Poängsamlingen bär samma stämplar som fastigheten med samma id
    stamps_by_id = {
        f["properties"]["id"]: (f["properties"]["created_at"], f["properties"]["updated_at"])
        for f in data["properties"]["features"]
    }
    for feature in data["proximityScores"]["features"]:
        props = feature["properties"]
        assert stamps_by_id[props["id"]] == (props["created_at"], props["updated_at"])


def test_sample_export_has_both_new_and_changed_objects():
    """Panelen "Nytt sedan senast" ska kunna visa båda händelsetyperna i demo-läge."""
    from scripts.export_sample_data import build_sample_data

    projects = build_sample_data()["infrastructureProjects"]["features"]
    changed = [
        f for f in projects if f["properties"]["updated_at"] != f["properties"]["created_at"]
    ]
    assert 0 < len(changed) < len(projects)
