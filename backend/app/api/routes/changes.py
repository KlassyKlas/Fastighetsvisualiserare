from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.schemas import ChangesResponse
from app.services import changes as changes_service

router = APIRouter()


@router.get("", response_model=ChangesResponse)
async def list_changes(
    session: SessionDep,
    since: Annotated[
        datetime,
        Query(
            description=(
                "Visa det som skapats eller ändrats efter denna tidpunkt "
                "(ISO 8601; naiv tid tolkas som UTC)"
            )
        ),
    ],
    limit: Annotated[
        int,
        Query(
            ge=0,
            le=500,
            description="Högsta antal händelser i svaret — 0 ger bara räkningarna (notisbadgen)",
        ),
    ] = 200,
) -> ChangesResponse:
    """Nytt sedan senast: nya och ändrade projekt och detaljplaner i hela datamängden.

    Globalt komplement till bevakningarna (som svarar per ritat område).
    Räkningarna gäller hela urvalet; händelselistan begränsas av limit
    med projekt först och detaljplaner därefter.
    """
    return await changes_service.changes(session, since=since, limit=limit)
