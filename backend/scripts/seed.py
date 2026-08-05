"""Ladda databasen med exempeldata (idempotent — kör gärna flera gånger).

uv run python -m scripts.seed
"""

import asyncio

from app.db import SessionFactory, engine
from app.seed_data import INFRASTRUCTURE_PROJECTS, PROPERTIES
from app.services.infrastructure import upsert_projects
from app.services.properties import upsert_properties


async def main() -> None:
    async with SessionFactory() as session:
        projects_upserted, projects_skipped = await upsert_projects(
            session, INFRASTRUCTURE_PROJECTS
        )
        properties_upserted, properties_skipped = await upsert_properties(session, PROPERTIES)
        await session.commit()

    await engine.dispose()

    print(f"Infrastrukturprojekt: {projects_upserted} inskrivna, {projects_skipped} överhoppade")
    print(f"Fastigheter: {properties_upserted} inskrivna, {properties_skipped} överhoppade")


if __name__ == "__main__":
    asyncio.run(main())
