from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import BboxDep, SessionDep, WriteAccess
from app.domain import PropertyType
from app.schemas import NearbyProjectsResponse, PropertyCollection, PropertyCreate, PropertyFeature
from app.services import analysis as analysis_service
from app.services import properties as property_service

router = APIRouter()


@router.get("", response_model=PropertyCollection)
async def list_properties(
    session: SessionDep,
    bbox: BboxDep,
    municipality: Annotated[
        list[str] | None, Query(description="Filtrera på kommun (kan upprepas)")
    ] = None,
    property_type: Annotated[
        list[PropertyType] | None,
        Query(description="Filtrera på fastighetstyp (kan upprepas)"),
    ] = None,
    min_value: Annotated[int | None, Query(ge=0, description="Lägsta taxeringsvärde (SEK)")] = None,
    max_value: Annotated[int | None, Query(ge=0, description="Högsta taxeringsvärde (SEK)")] = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PropertyCollection:
    """Fastigheter som GeoJSON FeatureCollection, med filter och paginering."""
    return await property_service.list_properties(
        session,
        municipalities=municipality,
        property_types=property_type,
        min_value=min_value,
        max_value=max_value,
        bbox=bbox,
        limit=limit,
        offset=offset,
    )


@router.get("/search", response_model=PropertyCollection)
async def search_properties(
    session: SessionDep,
    q: Annotated[str, Query(min_length=2, description="Sökterm")],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PropertyCollection:
    """Fritextsök på beteckning, adress, ägare, stad och kommun."""
    return await property_service.search_properties(session, q, limit)


@router.get("/{property_id}", response_model=PropertyFeature)
async def get_property(session: SessionDep, property_id: int) -> PropertyFeature:
    feature = await property_service.get_property(session, property_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Fastigheten hittades inte")
    return feature


@router.get("/{property_id}/nearby-projects", response_model=NearbyProjectsResponse)
async def nearby_projects(
    session: SessionDep,
    property_id: int,
    max_distance_m: Annotated[
        float, Query(gt=0, le=50_000, description="Maximalt avstånd i meter")
    ] = 5000,
) -> NearbyProjectsResponse:
    """Infrastrukturprojekt nära en fastighet, närmast först (ST_DWithin)."""
    result = await analysis_service.nearby_projects(session, property_id, max_distance_m)
    if result is None:
        raise HTTPException(status_code=404, detail="Fastigheten hittades inte")
    return result


@router.post("", response_model=PropertyFeature, status_code=201, dependencies=[WriteAccess])
async def create_property(session: SessionDep, data: PropertyCreate) -> PropertyFeature:
    return await property_service.create_property(session, data)
