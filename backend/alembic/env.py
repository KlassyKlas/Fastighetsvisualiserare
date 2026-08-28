import asyncio
from collections.abc import Callable
from logging.config import fileConfig

from geoalchemy2 import alembic_helpers
from sqlalchemy import text
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


def extension_owned_tables(connection: Connection) -> set[str]:
    """Tabeller som ägs av en PostgreSQL-extension (PostGIS, Tiger, topology).

    Precis den mängd tabeller som finns i databasen utan att ha modeller —
    legitimt. En egen tabell vars modell raderats utan drop-migration är
    inte extension-ägd och flaggas därmed fortfarande av alembic check.
    """
    rows = connection.execute(
        text(
            """
            SELECT c.relname
            FROM pg_class c
            JOIN pg_depend d ON d.objid = c.oid AND d.deptype = 'e'
            WHERE c.relkind IN ('r', 'p')
            """
        )
    )
    return set(rows.scalars())


def make_include_object(extension_tables: set[str]) -> Callable[..., bool]:
    """GeoAlchemy2:s filter + två källor till falsk drift i alembic check.

    1) PostGIS-imagen skeppar extension-ägda tabeller (spatial_ref_sys,
       tabblock20, layer, ...) som ligger i search_path men inte i våra
       modeller — de ska inte rapporteras som borttagna.
    2) De funktionella geography-indexen (idx_*_geometry_geog) jämförs
       textuellt och PostgreSQL normaliserar uttrycket
       ('geometry::geography(...)' ≠ 'CAST(geometry AS geography(...))')
       — evig falsk drift. Att indexen finns och castar till geography
       verifieras i stället av integrationstestet
       test_functional_geography_indexes_exist.
    """

    def include_object(
        obj: object, name: str | None, type_: str, reflected: bool, compare_to: object
    ) -> bool:
        if type_ == "table" and reflected and name in extension_tables:
            return False
        if type_ == "index" and name is not None and name.endswith("_geometry_geog"):
            return False
        return alembic_helpers.include_object(obj, name, type_, reflected, compare_to)

    return include_object


def run_migrations_offline() -> None:
    """Generera SQL utan databasanslutning (alembic upgrade --sql)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Offline-läget genererar bara SQL (ingen jämförelse mot en
        # databas) — extensionstabellerna behövs inte här.
        include_object=make_include_object(set()),
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
        include_object=make_include_object(extension_owned_tables(connection)),
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
