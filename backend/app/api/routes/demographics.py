from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import BboxDep, SessionDep
from app.schemas import DesoAreaCollection, DesoAreaFeature
from app.services import demographics as demographics_service

router = APIRouter()


@router.get("/deso-areas", response_model=DesoAreaCollection)
async def list_deso_areas(
    session: SessionDep,
    bbox: BboxDep,
    municipality_code: Annotated[
        list[str] | None,
        Query(description="Filtrera på kommunkod, t.ex. '0180' (kan upprepas)"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=6000)] = 2000,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DesoAreaCollection:
    """DeSO-områden med demografi som GeoJSON FeatureCollection.

    Geometrierna förenklas för kartbruk. Sverige har ~6000 DeSO —
    använd bbox (kartvyn) eller kommunkod för att begränsa svaret.
    """
    return await demographics_service.list_deso_areas(
        session,
        municipality_codes=municipality_code,
        bbox=bbox,
        limit=limit,
        offset=offset,
    )


@router.get("/deso-areas/lookup", response_model=DesoAreaFeature)
async def lookup_deso_area(
    session: SessionDep,
    lng: Annotated[float, Query(ge=-180, le=180, description="Longitud (WGS84)")],
    lat: Annotated[float, Query(ge=-90, le=90, description="Latitud (WGS84)")],
) -> DesoAreaFeature:
    """DeSO-området som innehåller punkten — områdesstatistik för en fastighet.

    Svarets geometry är null: uppslaget driver statistikvisning, inte kartritning.
    """
    feature = await demographics_service.lookup_deso_area(session, longitude=lng, latitude=lat)
    if feature is None:
        raise HTTPException(
            status_code=404,
            detail="Ingen DeSO-yta innehåller punkten — synkronisera SCB-källan först",
        )
    return feature
