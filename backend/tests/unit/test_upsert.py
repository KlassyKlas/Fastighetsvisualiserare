"""Enhetstester för den gemensamma upserten (utan databas): räkningarnas
aritmetik och ändringsdetekteringens SQL."""

from dataclasses import FrozenInstanceError

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models import InfrastructureProject
from app.services.upsert import SyncCounts, changed_where


def test_sync_counts_add_per_field():
    total = SyncCounts(upserted=2, unchanged=3) + SyncCounts(skipped=1) + SyncCounts(upserted=1)
    assert total == SyncCounts(upserted=3, unchanged=3, skipped=1)


def test_sync_counts_default_to_zero_and_are_immutable():
    counts = SyncCounts()
    assert (counts.upserted, counts.unchanged, counts.skipped) == (0, 0, 0)
    with pytest.raises(FrozenInstanceError):
        counts.upserted = 1  # type: ignore[misc]


def test_sync_counts_render_as_report_line():
    assert str(SyncCounts(upserted=3, unchanged=2)) == "3 inskrivna, 2 oförändrade, 0 överhoppade"


def test_changed_where_compares_every_data_column_but_the_key():
    values = {"external_id": "x", "name": "Bron", "budget_sek": 1, "geometry": None}
    stmt = pg_insert(InfrastructureProject).values(**values)
    clause = changed_where(stmt, InfrastructureProject, values, conflict_key="external_id")
    sql = str(clause.compile(dialect=postgresql.dialect()))

    assert "infrastructure_projects.name IS DISTINCT FROM excluded.name" in sql
    assert "infrastructure_projects.budget_sek IS DISTINCT FROM excluded.budget_sek" in sql
    # Konfliktnyckeln är per definition lika — den ska inte jämföras
    assert "excluded.external_id" not in sql
    # Geometrin jämförs med samma coalesce-regel som skrivningen: inkommande
    # NULL räknas inte som en ändring av en befintlig geometri
    assert (
        "coalesce(excluded.geometry, infrastructure_projects.geometry) "
        "IS DISTINCT FROM infrastructure_projects.geometry"
    ) in sql
