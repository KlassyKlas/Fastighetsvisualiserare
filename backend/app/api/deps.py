from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services.geo import parse_bbox

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def require_write_access(
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    """Skyddar skrivande endpoints när API_WRITE_KEY är satt.

    Utan konfigurerad nyckel (lokal utveckling) släpps anropet igenom.
    """
    expected = get_settings().api_write_key
    if expected and x_api_key != expected:
        raise HTTPException(
            status_code=401,
            detail="Ogiltig eller saknad X-API-Key för skrivande anrop",
        )


WriteAccess = Depends(require_write_access)


def bbox_query(
    bbox: Annotated[
        str | None,
        Query(description="Avgränsningsruta i WGS84: väst,syd,öst,norr"),
    ] = None,
) -> tuple[float, float, float, float] | None:
    if bbox is None:
        return None
    return parse_bbox(bbox)


BboxDep = Annotated[tuple[float, float, float, float] | None, Depends(bbox_query)]
