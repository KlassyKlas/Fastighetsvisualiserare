"""Detaljplaner (Lantmäteriet NGP) och DeSO-områden (SCB).

Revision ID: 0002
Revides: 0001

Handskriven migration (autogenerate kräver databas). Spatiala index
skapas explicit med GeoAlchemy2:s standardnamn, samma mönster som 0001.
Inga geography-index behövs: frågorna mot dessa tabeller är rena
geometrioperationer (ST_Intersects mot bbox, ST_Contains för
punktuppslag) — inga meterberäkningar.
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "detail_plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("plan_number", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("municipality", sa.String(), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("adopted_date", sa.Date(), nullable=True),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False
            ),
            nullable=True,
        ),
        sa.Column(
            "metadata_json",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_detail_plans")),
    )
    op.create_index("ix_detail_plans_external_id", "detail_plans", ["external_id"], unique=True)
    op.create_index("ix_detail_plans_source", "detail_plans", ["source"])
    op.create_index("ix_detail_plans_status", "detail_plans", ["status"])
    op.create_index("ix_detail_plans_municipality", "detail_plans", ["municipality"])
    op.create_index(
        "idx_detail_plans_geometry",
        "detail_plans",
        ["geometry"],
        postgresql_using="gist",
    )

    op.create_table(
        "deso_areas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("deso_code", sa.String(), nullable=False),
        sa.Column("municipality_code", sa.String(), nullable=True),
        sa.Column("municipality", sa.String(), nullable=True),
        sa.Column("population", sa.Integer(), nullable=True),
        sa.Column("population_year", sa.Integer(), nullable=True),
        sa.Column("mean_income_sek", sa.Integer(), nullable=True),
        sa.Column("higher_education_share", sa.Float(), nullable=True),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False
            ),
            nullable=True,
        ),
        sa.Column(
            "stats_json",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deso_areas")),
    )
    op.create_index("ix_deso_areas_deso_code", "deso_areas", ["deso_code"], unique=True)
    op.create_index("ix_deso_areas_municipality_code", "deso_areas", ["municipality_code"])
    op.create_index("ix_deso_areas_municipality", "deso_areas", ["municipality"])
    op.create_index(
        "idx_deso_areas_geometry",
        "deso_areas",
        ["geometry"],
        postgresql_using="gist",
    )


def downgrade() -> None:
    op.drop_table("deso_areas")
    op.drop_table("detail_plans")
