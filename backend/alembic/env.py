import asyncio
from logging.config import fileConfig

from geoalchemy2 import alembic_helpers
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.config import get_settings
from app.db import Base
from app.models import InfrastructureProject, Property  # noqa: F401  (fyller metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def include_object(obj: object, name: str | None, type_: str, reflected: bool, compare_to: object):
    """GeoAlchemy2:s filter + två källor till falsk drift i alembic check.

    1) PostGIS-imagen skeppar Tiger/topology-tabeller (tabblock20, layer,
       spatial_ref_sys, ...) som ligger i search_path men inte i våra
       modeller — de ska inte rapporteras som borttagna. Blind fläck:
       en modell som raderas utan drop-migration upptäcks inte heller.
    2) De funktionella geography-indexen (idx_*_geometry_geog) jämförs
       textuellt och PostgreSQL normaliserar uttrycket
       ('geometry::geography(...)' ≠ 'CAST(geometry AS geography(...))')
       — evig falsk drift. De förvaltas för hand i modell + migration.
    """
    if type_ == "table" and reflected and compare_to is None:
        return False
    if type_ == "index" and name is not None and name.endswith("_geometry_geog"):
        return False
    return alembic_helpers.include_object(obj, name, type_, reflected, compare_to)


def run_migrations_offline() -> None:
    """Generera SQL utan databasanslutning (alembic upgrade --sql)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        process_revision_directives=alembic_helpers.writer,
        render_item=alembic_helpers.render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # GeoAlchemy2:s hjälpare gör att autogenerate hanterar
        # geometrikolumner och spatiala index korrekt.
        include_object=include_object,
        process_revision_directives=alembic_helpers.writer,
        render_item=alembic_helpers.render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
