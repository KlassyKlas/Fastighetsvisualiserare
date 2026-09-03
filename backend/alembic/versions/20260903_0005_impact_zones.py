"""Förberäknade påverkanszoner (infrastructure_projects.impact_zone).

Revision ID: 0005
Revises: 0004

Handskriven migration (autogenerate kräver databas). Kolumnen är en
STORED generated column: PostgreSQL räknar zonen varje gång geometry
eller impact_radius_m skrivs, och fyller befintliga rader när kolumnen
läggs till (tabellen skrivs om — nationell plan-korridorerna tar några
sekunder). Uttrycket måste vara identiskt med IMPACT_ZONE_SQL i
app/models/infrastructure.py; alembic check varnar om de glider isär.
ST_Buffer(geography, float8) är IMMUTABLE i PostGIS, vilket generated
columns kräver. Spatialt index skapas explicit, samma mönster som 0002
(bbox-filtret i påverkanszonsfrågan går mot zonen, inte projektet).
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

IMPACT_ZONE_SQL = (
    "ST_SimplifyPreserveTopology(ST_Buffer(geometry::geography, impact_radius_m)::geometry, 0.0002)"
)


def upgrade() -> None:
    op.add_column(
        "infrastructure_projects",
        sa.Column(
            "impact_zone",
            geoalchemy2.types.Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False),
            sa.Computed(IMPACT_ZONE_SQL, persisted=True),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_infrastructure_projects_impact_zone",
        "infrastructure_projects",
        ["impact_zone"],
        postgresql_using="gist",
    )


def downgrade() -> None:
    op.drop_index("idx_infrastructure_projects_impact_zone", table_name="infrastructure_projects")
    op.drop_column("infrastructure_projects", "impact_zone")
