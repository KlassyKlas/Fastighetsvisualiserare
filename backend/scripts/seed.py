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


def _report(label: str, counts: tuple[int, int, int]) -> None:
    upserted, unchanged, skipped = counts
    print(f"{label}: {upserted} inskrivna, {unchanged} oförändrade, {skipped} överhoppade")


async def main() -> None:
    async with SessionFactory() as session:
        project_counts = await upsert_projects(session, INFRASTRUCTURE_PROJECTS)
        property_counts = await upsert_properties(session, PROPERTIES)
        plan_counts = await upsert_detail_plans(session, DETAIL_PLANS)
        deso_counts = await upsert_deso_areas(session, DESO_AREAS)
        await session.commit()

    await engine.dispose()

    _report("Infrastrukturprojekt", project_counts)
    _report("Fastigheter", property_counts)
    _report("Detaljplaner", plan_counts)
    _report("DeSO-områden", deso_counts)


if __name__ == "__main__":
    asyncio.run(main())
