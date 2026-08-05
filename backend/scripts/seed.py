"""Ladda databasen med exempeldata (idempotent — kör gärna flera gånger).

uv run python -m scripts.seed
"""

import asyncio

from app.db import SessionFactory, engine
from app.seed_data import DESO_AREAS, DETAIL_PLANS, INFRASTRUCTURE_PROJECTS, PROPERTIES
from app.services.demographics import upsert_deso_areas
from app.services.infrastructure import upsert_projects
from app.services.planning import upsert_detail_plans
from app.services.properties import upsert_properties


async def main() -> None:
    async with SessionFactory() as session:
        projects_upserted, projects_skipped = await upsert_projects(
            session, INFRASTRUCTURE_PROJECTS
        )
        properties_upserted, properties_skipped = await upsert_properties(session, PROPERTIES)
        plans_upserted, plans_skipped = await upsert_detail_plans(session, DETAIL_PLANS)
        deso_upserted, deso_skipped = await upsert_deso_areas(session, DESO_AREAS)
        await session.commit()

    await engine.dispose()

    print(f"Infrastrukturprojekt: {projects_upserted} inskrivna, {projects_skipped} överhoppade")
    print(f"Fastigheter: {properties_upserted} inskrivna, {properties_skipped} överhoppade")
    print(f"Detaljplaner: {plans_upserted} inskrivna, {plans_skipped} överhoppade")
    print(f"DeSO-områden: {deso_upserted} inskrivna, {deso_skipped} överhoppade")


if __name__ == "__main__":
    asyncio.run(main())
