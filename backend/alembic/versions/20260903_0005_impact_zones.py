"""Förberäknade påverkanszoner (infrastructure_projects.impact_zone).

Revision ID: 0005
Revises: 0004

Handskriven migration (autogenerate kräver databas). Kolumnen är en
genererad kolumn (GENERATED ALWAYS AS … STORED): PostgreSQL räknar zonen
varje gång geometry eller impact_radius_m skrivs, och fyller befintliga
rader när kolumnen läggs till (tabellen skrivs om under ACCESS
EXCLUSIVE-lås — nationell plan-korridorerna tar några sekunder).
Uttrycket är samma text som IMPACT_ZONE_SQL i app/models/infrastructure.py;
alembic check kan inte se drift i det (bara en varning), så likheten
vaktas av tester (se modellen). ST_Buffer(geography, float8) är IMMUTABLE
i PostGIS, vilket genererade kolumner kräver.

Finns en befintlig rad vars geometri inte kan castas till geography
(koordinater utanför WGS84 — t.ex. SWEREF 99 TM sparat som SRID 4326)
avbryts hela migrationen. Hitta sådana rader i förväg:

    SELECT id, name FROM infrastructure_projects
    WHERE geometry IS NOT NULL AND NOT (
        ST_XMin(geometry) >= -180 AND ST_XMax(geometry) <= 180
        AND ST_YMin(geometry) >= -90 AND ST_YMax(geometry) <= 90);

Nya sådana rader stoppas i app/services/geo.py innan de når databasen.
Spatialt index skapas explicit, samma mönster som 0002 (bbox-filtret i
påverkanszonsfrågan går mot zonen, inte projektet).
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
    "ST_SimplifyPreserveTopology("
    "ST_Buffer(geometry::geography, impact_radius_m)::geometry, 0.0002::double precision)"
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
