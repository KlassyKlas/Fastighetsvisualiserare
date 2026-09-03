"""Migration och modell måste vara överens om det alembic check inte kan
jämföra: uttrycket i en genererad kolumn ger bara en varning, aldrig en
schemaskillnad. Återskapas kolumnen i en senare migration pekas
MIGRATION om dit."""

import importlib.util
from pathlib import Path

from app.models.infrastructure import IMPACT_ZONE_SQL

MIGRATION = (
    Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20260903_0005_impact_zones.py"
)


def test_migration_and_model_agree_on_impact_zone():
    spec = importlib.util.spec_from_file_location("migration_0005_impact_zones", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.IMPACT_ZONE_SQL == IMPACT_ZONE_SQL
