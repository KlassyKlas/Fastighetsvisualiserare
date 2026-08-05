"""Kontraktstester: API-ytan som frontenden är genererad mot.

Om en path försvinner eller byter namn faller detta test — samma garanti
som frontendens typgenerering ger vid kompilering, fast redan i backend.
"""

from app.domain import ProjectStatus, ProjectType, PropertyType
from app.main import app

EXPECTED_PATHS = {
    "/api/v1/health",
    "/api/v1/properties",
    "/api/v1/properties/search",
    "/api/v1/properties/{property_id}",
    "/api/v1/properties/{property_id}/nearby-projects",
    "/api/v1/infrastructure/projects",
    "/api/v1/infrastructure/projects/{project_id}",
    "/api/v1/infrastructure/impact-zones",
    "/api/v1/infrastructure/sources",
    "/api/v1/infrastructure/sync/{source_name}",
    "/api/v1/analysis/affected-properties",
    "/api/v1/analysis/proximity-scores",
}


def test_all_expected_paths_exist():
    spec = app.openapi()
    assert set(spec["paths"].keys()) == EXPECTED_PATHS


def test_domain_enums_in_openapi_schema():
    spec = app.openapi()
    schemas = spec["components"]["schemas"]

    assert set(schemas["ProjectStatus"]["enum"]) == {s.value for s in ProjectStatus}
    assert set(schemas["ProjectType"]["enum"]) == {t.value for t in ProjectType}
    assert set(schemas["PropertyType"]["enum"]) == {t.value for t in PropertyType}


def test_collections_carry_pagination_metadata():
    spec = app.openapi()
    schemas = spec["components"]["schemas"]
    for name in ("PropertyCollection", "InfrastructureProjectCollection"):
        assert "numberMatched" in schemas[name]["properties"]
        assert "numberReturned" in schemas[name]["properties"]
