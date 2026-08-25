"""Integrationstester mot en riktig PostGIS-databas.

Körs bara när INTEGRATION_TESTS=1 (CI startar en postgis-service och
kör `alembic upgrade head` först). Lokalt:

    docker compose up -d db
    uv run alembic upgrade head
    INTEGRATION_TESTS=1 uv run pytest tests/integration
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import SessionFactory
from app.seed_data import INFRASTRUCTURE_PROJECTS, PROPERTIES
from app.services.infrastructure import upsert_projects
from app.services.properties import upsert_properties

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("INTEGRATION_TESTS") != "1",
        reason="Sätt INTEGRATION_TESTS=1 och peka DATABASE_URL mot en PostGIS-databas",
    ),
    pytest.mark.asyncio(loop_scope="session"),
]

STOCKHOLM_BBOX = "17.5,59.0,18.5,59.7"


@pytest.fixture(scope="session")
async def client():
    from app.main import app

    async with SessionFactory() as session:
        await upsert_projects(session, INFRASTRUCTURE_PROJECTS)
        await upsert_properties(session, PROPERTIES)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_health(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


async def test_list_properties(client):
    response = await client.get("/api/v1/properties")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert data["numberMatched"] >= 10
    assert data["numberReturned"] == len(data["features"])
    first = data["features"][0]
    assert first["geometry"]["type"] == "MultiPolygon"
    assert isinstance(first["properties"]["id"], int)


async def test_pagination(client):
    response = await client.get("/api/v1/properties", params={"limit": 3, "offset": 0})
    data = response.json()
    assert data["numberReturned"] == 3
    assert data["numberMatched"] >= 10

    page2 = (await client.get("/api/v1/properties", params={"limit": 3, "offset": 3})).json()
    ids_page1 = {f["properties"]["id"] for f in data["features"]}
    ids_page2 = {f["properties"]["id"] for f in page2["features"]}
    assert ids_page1.isdisjoint(ids_page2)


async def test_bbox_filter_excludes_gothenburg(client):
    response = await client.get("/api/v1/properties", params={"bbox": STOCKHOLM_BBOX})
    municipalities = {f["properties"]["municipality"] for f in response.json()["features"]}
    assert "Stockholm" in municipalities

    projects = (
        await client.get("/api/v1/infrastructure/projects", params={"bbox": STOCKHOLM_BBOX})
    ).json()
    names = {f["properties"]["name"] for f in projects["features"]}
    assert "Västlänken" not in names  # Göteborg
    assert "Nya Slussen" in names


async def test_invalid_bbox_gives_400(client):
    response = await client.get("/api/v1/properties", params={"bbox": "1,2,3"})
    assert response.status_code == 400


async def test_repeated_status_filter(client):
    response = await client.get(
        "/api/v1/infrastructure/projects",
        params=[("status", "planerad"), ("status", "avslutad")],
    )
    statuses = {f["properties"]["status"] for f in response.json()["features"]}
    assert statuses <= {"planerad", "avslutad"}
    assert "pågående" not in statuses


async def test_impact_zones_include_line_projects(client):
    response = await client.get("/api/v1/infrastructure/impact-zones")
    assert response.status_code == 200
    zones = response.json()["features"]
    by_name = {z["properties"]["name"]: z for z in zones}
    # Förbifart Stockholm är en LINJE — den ska också få en buffrad zon
    zone = by_name["Förbifart Stockholm"]
    assert zone["geometry"]["type"] in ("Polygon", "MultiPolygon")
    assert zone["properties"]["impact_radius_m"] == 3000


async def test_nearby_projects(client):
    # Hitta Södermalm 3:12 (ca 500 m från Nya Slussen)
    search = await client.get("/api/v1/properties/search", params={"q": "Södermalm 3:12"})
    prop_id = search.json()["features"][0]["properties"]["id"]

    response = await client.get(f"/api/v1/properties/{prop_id}/nearby-projects")
    assert response.status_code == 200
    data = response.json()
    names = [p["project"]["name"] for p in data["projects"]]
    assert "Nya Slussen" in names

    distances = [p["distance_m"] for p in data["projects"]]
    assert distances == sorted(distances)

    slussen = next(p for p in data["projects"] if p["project"]["name"] == "Nya Slussen")
    assert slussen["distance_m"] < 1500
    assert slussen["within_impact_radius"] is True


async def test_affected_properties(client):
    response = await client.get("/api/v1/analysis/affected-properties")
    assert response.status_code == 200
    data = response.json()
    assert data["numberReturned"] >= 1
    designations = {f["properties"]["designation"] for f in data["features"]}
    # Södermalm 3:12 ligger inom Nya Slussens påverkansradie (1000 m)
    assert "Södermalm 3:12" in designations
    feature = next(
        f for f in data["features"] if f["properties"]["designation"] == "Södermalm 3:12"
    )
    assert any(p["name"] == "Nya Slussen" for p in feature["properties"]["affecting_projects"])


async def test_create_property_and_conflict(client):
    payload = {
        "designation": "Testfastighet 99:1",
        "municipality": "Stockholm",
        "property_type": "kontor",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[18.0, 59.0], [18.01, 59.0], [18.01, 59.01], [18.0, 59.01], [18.0, 59.0]]
            ],
        },
    }
    response = await client.post("/api/v1/properties", json=payload)
    assert response.status_code == 201
    created = response.json()
    # SRID-hantering: geometrin ska ha sparats och komma tillbaka som MultiPolygon
    assert created["geometry"]["type"] == "MultiPolygon"

    duplicate = await client.post("/api/v1/properties", json=payload)
    assert duplicate.status_code == 409


async def test_create_with_invalid_geometry_gives_422(client):
    response = await client.post(
        "/api/v1/properties",
        json={"designation": "Trasig 1:1", "geometry": {"type": "Nonsens"}},
    )
    assert response.status_code == 422


async def test_create_property_with_point_geometry_gives_422(client):
    response = await client.post(
        "/api/v1/properties",
        json={
            "designation": "Punktfastighet 1:1",
            "geometry": {"type": "Point", "coordinates": [18.0, 59.0]},
        },
    )
    assert response.status_code == 422


async def test_proximity_scores(client):
    response = await client.get("/api/v1/analysis/proximity-scores")
    assert response.status_code == 200
    data = response.json()
    assert data["numberReturned"] >= 1

    scores = [f["properties"]["score"] for f in data["features"]]
    assert scores == sorted(scores, reverse=True)
    ranks = [f["properties"]["rank"] for f in data["features"]]
    assert ranks == list(range(1, len(ranks) + 1))

    top = data["features"][0]["properties"]
    assert top["contributions"]
    assert top["score"] == round(sum(c["points"] for c in top["contributions"]), 1)
    # Bidragen är sorterade med största först
    points = [c["points"] for c in top["contributions"]]
    assert points == sorted(points, reverse=True)


async def test_proximity_scores_respects_year(client):
    response = await client.get("/api/v1/analysis/proximity-scores", params={"year": 2010})
    assert response.status_code == 200
    for feature in response.json()["features"]:
        names = {c["name"] for c in feature["properties"]["contributions"]}
        # Tvärförbindelse Södertörn (2025–2032) var inte aktiv 2010
        assert "Tvärförbindelse Södertörn" not in names


async def test_year_filter_on_projects(client):
    response = await client.get("/api/v1/infrastructure/projects", params={"year": 2012})
    names = {f["properties"]["name"] for f in response.json()["features"]}
    assert "Citybanan" in names  # aktiv 2009–2017
    assert "Tvärförbindelse Södertörn" not in names  # 2025–2032

    zones = await client.get("/api/v1/infrastructure/impact-zones", params={"year": 2012})
    zone_names = {f["properties"]["name"] for f in zones.json()["features"]}
    assert "Citybanan" in zone_names
    assert "Tvärförbindelse Södertörn" not in zone_names


async def test_sync_unknown_source_gives_404(client):
    response = await client.post("/api/v1/infrastructure/sync/finnsinte")
    assert response.status_code == 404
    assert "trafikverket" in response.json()["detail"]


async def test_sources_listed(client):
    response = await client.get("/api/v1/infrastructure/sources")
    sources = response.json()
    assert "trafikverket" in sources
    assert sources["nationell_plan"] == "Trafikverket (nationell plan)"


async def test_watch_lifecycle(client):
    # Skapa en bevakning över Stockholms innerstad
    payload = {
        "name": "Innerstan",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[17.9, 59.2], [18.3, 59.2], [18.3, 59.4], [17.9, 59.4], [17.9, 59.2]]],
        },
    }
    created = await client.post("/api/v1/watches", json=payload)
    assert created.status_code == 201
    watch = created.json()
    assert watch["geometry"]["type"] == "MultiPolygon"
    assert watch["properties"]["last_seen_at"] is not None  # börjar "ren"
    watch_id = watch["properties"]["id"]

    listed = await client.get("/api/v1/watches")
    assert watch_id in {f["properties"]["id"] for f in listed.json()["features"]}

    # Direkt efter skapandet: projekt i området räknas, men inga händelser
    events = (await client.get("/api/v1/watches/events")).json()
    entry = next(w for w in events["watches"] if w["watch_id"] == watch_id)
    assert entry["project_count"] >= 1  # Nya Slussen m.fl. ligger i rutan
    assert entry["project_events"] == []

    # Rör ett projekt i området — synkupserten flyttar fram updated_at
    async with SessionFactory() as session:
        await upsert_projects(session, INFRASTRUCTURE_PROJECTS)
        await session.commit()

    events = (await client.get("/api/v1/watches/events")).json()
    entry = next(w for w in events["watches"] if w["watch_id"] == watch_id)
    assert len(entry["project_events"]) >= 1
    assert {e["event_kind"] for e in entry["project_events"]} == {"ändrat"}
    assert events["total_events"] >= 1

    # Markera som sett — händelserna nollställs
    seen = await client.post(f"/api/v1/watches/{watch_id}/mark-seen")
    assert seen.status_code == 200
    events = (await client.get("/api/v1/watches/events")).json()
    entry = next(w for w in events["watches"] if w["watch_id"] == watch_id)
    assert entry["project_events"] == []
    assert entry["project_count"] >= 1  # innehållet finns kvar, bara sett

    deleted = await client.delete(f"/api/v1/watches/{watch_id}")
    assert deleted.status_code == 204
    assert (await client.delete(f"/api/v1/watches/{watch_id}")).status_code == 404


async def test_watch_with_point_geometry_gives_422(client):
    response = await client.post(
        "/api/v1/watches",
        json={"name": "Punkt", "geometry": {"type": "Point", "coordinates": [18.0, 59.3]}},
    )
    assert response.status_code == 422
