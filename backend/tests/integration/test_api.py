"""Integrationstester mot en riktig PostGIS-databas.

Körs bara när INTEGRATION_TESTS=1 (CI startar en postgis-service och
kör `alembic upgrade head` först). Lokalt:

    docker compose up -d db
    uv run alembic upgrade head
    INTEGRATION_TESTS=1 uv run pytest tests/integration
"""

import os
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.datasources import Bbox, DataSource, DataSourceError, InfrastructureProjectIngest
from app.datasources.base import _registry
from app.db import SessionFactory
from app.models import SyncRun
from app.seed_data import DETAIL_PLANS, INFRASTRUCTURE_PROJECTS, PROPERTIES
from app.services import infrastructure as infrastructure_service
from app.services.infrastructure import upsert_projects
from app.services.planning import upsert_detail_plans
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
        await upsert_detail_plans(session, DETAIL_PLANS)
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

    # Oförändrad omsynkning får INTE flytta updated_at och tända notiser —
    # ändringsdetekteringen i upserten lämnar identiska rader orörda
    async with SessionFactory() as session:
        upserted, unchanged, skipped = await upsert_projects(session, INFRASTRUCTURE_PROJECTS)
        await session.commit()
    assert upserted == 0
    assert unchanged == len(INFRASTRUCTURE_PROJECTS)
    assert skipped == 0

    events = (await client.get("/api/v1/watches/events")).json()
    entry = next(w for w in events["watches"] if w["watch_id"] == watch_id)
    assert entry["project_events"] == []

    # En FAKTISK ändring ger exakt en "ändrat"-händelse för det projektet
    slussen = next(p for p in INFRASTRUCTURE_PROJECTS if p.name == "Nya Slussen")
    modified = slussen.model_copy(update={"budget_sek": (slussen.budget_sek or 0) + 1})
    async with SessionFactory() as session:
        upserted, unchanged, _ = await upsert_projects(session, [modified])
        await session.commit()
    assert (upserted, unchanged) == (1, 0)

    events = (await client.get("/api/v1/watches/events")).json()
    entry = next(w for w in events["watches"] if w["watch_id"] == watch_id)
    changed_names = [e["project"]["properties"]["name"] for e in entry["project_events"]]
    assert changed_names == ["Nya Slussen"]
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


async def test_functional_geography_indexes_exist():
    """De funktionella geography-indexen kan inte jämföras av alembic check
    (PostgreSQL normaliserar uttrycket; filtreras därför i alembic/env.py)
    — verifiera i stället här att de finns, är GiST och castar till
    geography. Utan dem kör analysfrågorna oindexerat."""
    async with SessionFactory() as session:
        rows = await session.execute(
            text(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE indexname LIKE 'idx\\_%\\_geometry\\_geog'
                """
            )
        )
        index_defs = {name: definition.lower() for name, definition in rows.all()}

    for index_name in (
        "idx_properties_geometry_geog",
        "idx_infrastructure_projects_geometry_geog",
    ):
        assert index_name in index_defs, f"{index_name} saknas i databasen"
        assert "using gist" in index_defs[index_name]
        assert "::geography(geometry,4326)" in index_defs[index_name]


async def test_watch_with_point_geometry_gives_422(client):
    response = await client.post(
        "/api/v1/watches",
        json={"name": "Punkt", "geometry": {"type": "Point", "coordinates": [18.0, 59.3]}},
    )
    assert response.status_code == 422


# --- Punkt 7: Nytt sedan senast ---------------------------------------------

LONG_AGO = "2000-01-01T00:00:00Z"


async def test_changes_since_long_ago_lists_seed_as_new(client):
    response = await client.get("/api/v1/changes", params={"since": LONG_AGO, "limit": 500})
    assert response.status_code == 200
    data = response.json()
    assert datetime.fromisoformat(data["since"]) == datetime(2000, 1, 1, tzinfo=UTC)

    # Allt i seeden är skapat efter 2000 → "nytt", aldrig "ändrat"
    assert data["project_new"] >= len(INFRASTRUCTURE_PROJECTS)
    assert data["plan_new"] >= len(DETAIL_PLANS)
    assert data["project_changed"] == 0
    assert data["plan_changed"] == 0
    assert data["total_events"] == (
        data["project_new"] + data["project_changed"] + data["plan_new"] + data["plan_changed"]
    )
    assert data["truncated"] is False
    assert len(data["project_events"]) + len(data["plan_events"]) == data["total_events"]

    assert {e["event_kind"] for e in data["project_events"]} == {"nytt"}
    project_names = {e["project"]["properties"]["name"] for e in data["project_events"]}
    assert project_names >= {p.name for p in INFRASTRUCTURE_PROJECTS}
    plan_names = {e["plan"]["properties"]["name"] for e in data["plan_events"]}
    assert plan_names >= {p.name for p in DETAIL_PLANS}
    assert data["plan_events"][0]["plan"]["geometry"]["type"] == "MultiPolygon"

    # Senast ändrade först (parsa — strängjämförelse faller på mikrosekunderna)
    stamps = [
        datetime.fromisoformat(e["project"]["properties"]["updated_at"])
        for e in data["project_events"]
    ]
    assert stamps == sorted(stamps, reverse=True)


async def test_changes_in_future_is_empty(client):
    response = await client.get("/api/v1/changes", params={"since": "2999-01-01T00:00:00Z"})
    assert response.status_code == 200
    data = response.json()
    assert data["project_events"] == []
    assert data["plan_events"] == []
    assert data["total_events"] == 0
    assert data["truncated"] is False


async def test_changes_limit_truncates_but_keeps_totals(client):
    full = (await client.get("/api/v1/changes", params={"since": LONG_AGO, "limit": 500})).json()

    limited = (await client.get("/api/v1/changes", params={"since": LONG_AGO, "limit": 1})).json()
    assert limited["truncated"] is True
    assert limited["total_events"] == full["total_events"]
    # Projekten fyller listan först — planerna får det som blir över (inget)
    assert len(limited["project_events"]) == 1
    assert limited["plan_events"] == []

    # Precis ett steg över projekten: alla projekt + en plan, resten trunkerat
    project_total = full["project_new"] + full["project_changed"]
    plan_total = full["plan_new"] + full["plan_changed"]
    mixed = (
        await client.get("/api/v1/changes", params={"since": LONG_AGO, "limit": project_total + 1})
    ).json()
    assert len(mixed["project_events"]) == project_total
    assert len(mixed["plan_events"]) == 1
    assert mixed["truncated"] is (plan_total > 1)
    assert mixed["total_events"] == full["total_events"]


async def test_changes_accepts_naive_since_as_utc(client):
    response = await client.get("/api/v1/changes", params={"since": "2000-01-01T00:00:00"})
    assert response.status_code == 200
    since = datetime.fromisoformat(response.json()["since"])
    assert since.tzinfo is not None
    assert since == datetime(2000, 1, 1, tzinfo=UTC)


async def test_changes_requires_since(client):
    assert (await client.get("/api/v1/changes")).status_code == 422


async def test_changes_limit_zero_gives_only_counts(client):
    """limit=0 är notisbadgens läge: räkningarna utan en enda geometri i svaret."""
    response = await client.get("/api/v1/changes", params={"since": LONG_AGO, "limit": 0})
    assert response.status_code == 200
    data = response.json()
    assert data["project_events"] == [] and data["plan_events"] == []
    assert data["total_events"] >= len(INFRASTRUCTURE_PROJECTS)
    assert data["truncated"] is True


async def test_changes_reports_modified_project_as_changed(client):
    # Tidsankaret tas ur databasen så att app- och databasklocka inte kan skilja sig
    async with SessionFactory() as session:
        before = await session.scalar(select(func.now()))
    assert before is not None

    ostlanken = next(p for p in INFRASTRUCTURE_PROJECTS if p.external_id == "seed-ostlanken")
    modified = ostlanken.model_copy(update={"budget_sek": (ostlanken.budget_sek or 0) + 1})
    async with SessionFactory() as session:
        upserted, _, _ = await upsert_projects(session, [modified])
        await session.commit()
    assert upserted == 1

    data = (await client.get("/api/v1/changes", params={"since": before.isoformat()})).json()
    kinds = {e["project"]["properties"]["name"]: e["event_kind"] for e in data["project_events"]}
    assert kinds[ostlanken.name] == "ändrat"
    assert data["project_changed"] >= 1
    assert data["total_events"] >= 1


# --- Punkt 7: synklogg -------------------------------------------------------


async def test_sync_runs_are_listed_latest_first(client):
    async with SessionFactory() as session:
        run = SyncRun(
            source="testkälla", fetched=3, upserted=2, unchanged=1, finished_at=func.now()
        )
        session.add(run)
        await session.commit()
        run_id = run.id

    response = await client.get("/api/v1/infrastructure/sync/runs", params={"limit": 5})
    assert response.status_code == 200
    runs = response.json()["runs"]
    assert 1 <= len(runs) <= 5
    assert runs[0]["id"] == run_id  # nyast först
    assert runs[0]["source"] == "testkälla"
    assert runs[0]["finished_at"] is not None
    assert runs[0]["error"] is None
    assert runs[0]["truncated"] is False
    counts = (runs[0]["fetched"], runs[0]["upserted"], runs[0]["unchanged"], runs[0]["skipped"])
    assert counts == (3, 2, 1, 0)  # skipped via server_default

    starts = [datetime.fromisoformat(r["started_at"]) for r in runs]
    assert starts == sorted(starts, reverse=True)

    bad = await client.get("/api/v1/infrastructure/sync/runs", params={"limit": 0})
    assert bad.status_code == 422

    filtered = await client.get(
        "/api/v1/infrastructure/sync/runs", params={"source": "testkälla", "limit": 200}
    )
    assert {r["source"] for r in filtered.json()["runs"]} == {"testkälla"}
    assert filtered.json()["runs"][0]["id"] == run_id


class _FailingSource(DataSource):
    name = "testkalla_fel"
    display_name = "Testkälla (fel)"

    async def fetch_infrastructure_projects(
        self, bbox: Bbox | None = None
    ) -> list[InfrastructureProjectIngest]:
        raise DataSourceError(self.name, "nere för underhåll")


class _TinySource(DataSource):
    name = "testkalla_ok"
    display_name = "Testkälla (ok)"

    async def fetch_infrastructure_projects(
        self, bbox: Bbox | None = None
    ) -> list[InfrastructureProjectIngest]:
        return [INFRASTRUCTURE_PROJECTS[0]]


async def test_failed_sync_is_logged_with_error(client, monkeypatch):
    monkeypatch.setitem(_registry, _FailingSource.name, _FailingSource)

    response = await client.post(f"/api/v1/infrastructure/sync/{_FailingSource.name}")
    assert response.status_code == 502

    # Raden skapades före hämtningen och stängdes med felet
    runs = (await client.get("/api/v1/infrastructure/sync/runs")).json()["runs"]
    run = next(r for r in runs if r["source"] == _FailingSource.name)
    assert "nere för underhåll" in run["error"]
    assert run["finished_at"] is not None
    assert (run["fetched"], run["upserted"], run["unchanged"], run["skipped"]) == (0, 0, 0, 0)


async def test_successful_sync_returns_run_and_logs_counts(client, monkeypatch):
    monkeypatch.setitem(_registry, _TinySource.name, _TinySource)

    response = await client.post(f"/api/v1/infrastructure/sync/{_TinySource.name}")
    assert response.status_code == 200
    result = response.json()
    assert result["fetched"] == 1
    # Seedprojektet finns redan oförändrat i databasen
    assert (result["upserted"], result["unchanged"], result["skipped"]) == (0, 1, 0)
    assert isinstance(result["run_id"], int)
    assert datetime.fromisoformat(result["started_at"]).tzinfo is not None

    runs = (await client.get("/api/v1/infrastructure/sync/runs")).json()["runs"]
    run = next(r for r in runs if r["id"] == result["run_id"])
    assert run["source"] == _TinySource.name
    assert run["error"] is None
    assert run["finished_at"] is not None
    assert (run["fetched"], run["upserted"], run["unchanged"]) == (1, 0, 1)
    assert datetime.fromisoformat(run["started_at"]) == datetime.fromisoformat(result["started_at"])


class _CrashSource(_TinySource):
    name = "testkalla_krasch"
    display_name = "Testkälla (krasch efter hämtning)"


async def test_sync_crash_after_fetch_closes_run_with_error(client, monkeypatch):
    """Ett fel efter hämtningen får inte lämna loggraden som 'pågår' för evigt."""
    monkeypatch.setitem(_registry, _CrashSource.name, _CrashSource)

    async def exploding_upsert(session, items):
        # Ett riktigt databasfel: Postgres sätter transaktionen i avbrutet
        # läge, så loggraden kan bara stängas om sessionen rullats tillbaka.
        await session.execute(text("SELECT * FROM tabell_som_inte_finns"))
        raise AssertionError("nås aldrig")

    monkeypatch.setattr(infrastructure_service, "upsert_projects", exploding_upsert)

    # Appen har inga egna felhanterare: Starlette svarar 500 och kastar
    # vidare, och httpx ASGITransport lyfter undantaget till testet.
    with pytest.raises(SQLAlchemyError):
        await client.post(f"/api/v1/infrastructure/sync/{_CrashSource.name}")

    runs = (await client.get("/api/v1/infrastructure/sync/runs")).json()["runs"]
    run = next(r for r in runs if r["source"] == _CrashSource.name)
    assert run["finished_at"] is not None
    # Kurerad text: klassnamnet, aldrig SQL-satsen (loggen läses utan nyckel)
    assert run["error"].startswith("Oväntat fel (")
    assert "tabell_som_inte_finns" not in run["error"]
    # Inget hann skrivas — räkningarna står kvar på sina defaultvärden
    assert (run["fetched"], run["upserted"], run["unchanged"], run["skipped"]) == (0, 0, 0, 0)


# --- Punkt 7/8: detaljplan per id --------------------------------------------


async def test_get_detail_plan(client):
    listed = (await client.get("/api/v1/planning/detail-plans")).json()
    assert listed["numberMatched"] >= len(DETAIL_PLANS)
    plan_id = next(
        f["properties"]["id"]
        for f in listed["features"]
        if f["properties"]["external_id"] == "seed-dp-hagastaden"
    )

    response = await client.get(f"/api/v1/planning/detail-plans/{plan_id}")
    assert response.status_code == 200
    plan = response.json()
    assert plan["properties"]["name"] == "Detaljplan för Hagastaden etapp 3"
    assert plan["properties"]["municipality"] == "Stockholm"
    assert plan["geometry"]["type"] == "MultiPolygon"


async def test_get_unknown_detail_plan_gives_404(client):
    response = await client.get("/api/v1/planning/detail-plans/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Detaljplanen hittades inte"


# --- Punkt 9: ägarvy ---------------------------------------------------------

URW = "Unibail-Rodamco-Westfield"


async def test_owners_grouped_and_sorted(client):
    response = await client.get("/api/v1/properties/owners")
    assert response.status_code == 200
    data = response.json()
    owners = data["owners"]
    assert data["numberMatched"] >= len(owners) >= 2
    assert data["numberReturned"] == len(owners)

    counts = [o["property_count"] for o in owners]
    assert counts == sorted(counts, reverse=True)
    # Enda ägaren med två fastigheter i seeden — därför överst
    assert owners[0]["owner_name"] == URW

    urw = owners[0]
    assert urw["property_count"] == 2
    assert urw["owner_org_number"] == "556079-1415"
    assert urw["municipalities"] == ["Solna", "Täby"]
    assert urw["total_area_sqm"] == 12_000 + 15_000
    assert urw["total_assessed_value_sek"] == 350_000_000 + 280_000_000

    west, south, east, north = urw["extent"]
    assert west < east and south < north
    # Utbredningen täcker både Solna (18.00, 59.36) och Täby (18.07, 59.44)
    assert west <= 18.00 <= east and west <= 18.07 <= east
    assert south <= 59.36 <= north and south <= 59.44 <= north

    limited = (await client.get("/api/v1/properties/owners", params={"limit": 2})).json()
    assert len(limited["owners"]) == 2
    assert limited["numberMatched"] == data["numberMatched"]


async def test_owner_filter_on_properties(client):
    response = await client.get("/api/v1/properties", params={"owner": URW})
    assert response.status_code == 200
    data = response.json()
    assert {f["properties"]["owner_name"] for f in data["features"]} == {URW}
    assert data["numberMatched"] == data["numberReturned"] == 2

    # Exakt match — inte fritext
    partial = (await client.get("/api/v1/properties", params={"owner": "Unibail"})).json()
    assert partial["numberMatched"] == 0


async def test_owners_municipality_filter(client):
    response = await client.get("/api/v1/properties/owners", params={"municipality": "Täby"})
    assert response.status_code == 200
    owners = response.json()["owners"]
    urw = next(o for o in owners if o["owner_name"] == URW)
    assert urw["property_count"] == 1
    assert urw["municipalities"] == ["Täby"]
    assert all(o["municipalities"] == ["Täby"] for o in owners)
