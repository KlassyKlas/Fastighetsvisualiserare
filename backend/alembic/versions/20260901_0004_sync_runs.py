"""Synkroniseringslogg (sync_runs).

Revision ID: 0004
Revises: 0003

Handskriven migration (autogenerate kräver databas) — samma mönster som
0003. Tabellen saknar geometri, så inga spatiala index. Räkningarna får
server_default 0 och truncated false eftersom raden skapas INNAN
hämtningen (se app.services.infrastructure.sync_source) och ska vara
komplett redan innan utfallet är känt. Indexet på source heter som
SQLAlchemys namnkonvention ger (ix_sync_runs_source) så att alembic
check inte rapporterar drift mot modellen.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("upserted", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("unchanged", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("skipped", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("truncated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_runs")),
    )
    op.create_index(op.f("ix_sync_runs_source"), "sync_runs", ["source"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sync_runs_source"), table_name="sync_runs")
    op.drop_table("sync_runs")
