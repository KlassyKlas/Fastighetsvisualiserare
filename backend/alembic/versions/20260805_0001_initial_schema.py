"""Initialt schema: properties och infrastructure_projects med PostGIS.

Revision ID: 0001
Revides: None

Handskriven initial migration. Spatiala index skapas explicit med
GeoAlchemy2:s standardnamn (idx_<tabell>_<kolumn>) så att framtida
autogenerate inte ser någon drift.
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "properties",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("designation", sa.String(), nullable=False),
        sa.Column("municipality", sa.String(), nullable=True),
        sa.Column("county", sa.String(), nullable=True),
        sa.Column("area_sqm", sa.Float(), nullable=True),
        sa.Column("assessed_value_sek", sa.BigInteger(), nullable=True),
        sa.Column("property_type", sa.String(), nullable=True),
        sa.Column("owner_name", sa.String(), nullable=True),
        sa.Column("owner_org_number", sa.String(), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("postal_code", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False
            ),
            nullable=True,
        ),
        sa.Column("building_year", sa.Integer(), nullable=True),
        sa.Column("living_area_sqm", sa.Float(), nullable=True),
        sa.Column("zoning", sa.String(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_properties")),
    )
    op.create_index("ix_properties_designation", "properties", ["designation"], unique=True)
    op.create_index("ix_properties_municipality", "properties", ["municipality"])
    op.create_index("ix_properties_property_type", "properties", ["property_type"])
    op.create_index(
        "idx_properties_geometry",
        "properties",
        ["geometry"],
        postgresql_using="gist",
    )
    # Funktionellt index för geography-frågor (ST_DWithin/ST_Buffer i meter)
    op.execute(
        "CREATE INDEX idx_properties_geometry_geog "
        "ON properties USING gist (CAST(geometry AS geography))"
    )

    op.create_table(
        "infrastructure_projects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_type", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("budget_sek", sa.BigInteger(), nullable=True),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False),
            nullable=True,
        ),
        sa.Column("impact_radius_m", sa.Float(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_infrastructure_projects")),
    )
    op.create_index(
        "ix_infrastructure_projects_external_id",
        "infrastructure_projects",
        ["external_id"],
        unique=True,
    )
    op.create_index("ix_infrastructure_projects_source", "infrastructure_projects", ["source"])
    op.create_index(
        "ix_infrastructure_projects_project_type",
        "infrastructure_projects",
        ["project_type"],
    )
    op.create_index("ix_infrastructure_projects_status", "infrastructure_projects", ["status"])
    op.create_index(
        "idx_infrastructure_projects_geometry",
        "infrastructure_projects",
        ["geometry"],
        postgresql_using="gist",
    )
    op.execute(
        "CREATE INDEX idx_infrastructure_projects_geometry_geog "
        "ON infrastructure_projects USING gist (CAST(geometry AS geography))"
    )


def downgrade() -> None:
    op.drop_table("infrastructure_projects")
    op.drop_table("properties")
    # postgis-extensionen lämnas kvar — andra scheman kan bero på den
