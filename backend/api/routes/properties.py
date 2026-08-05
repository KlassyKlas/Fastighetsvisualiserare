import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2.functions import ST_MakeEnvelope, ST_Within
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database.connection import get_db
from models.property import Property
from schemas.property import (
    PropertyCollection,
    PropertyCreate,
    PropertyFeature,
    PropertyProperties,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def model_to_feature(prop: Property) -> dict:
    """Convert a Property SQLAlchemy model to a GeoJSON Feature dict."""
    geometry = None
    if prop.geometry is not None:
        try:
            shape = to_shape(prop.geometry)
            geometry = mapping(shape)
        except Exception:
            logger.warning("Failed to convert geometry for property %s", prop.id)

    properties = {
        "id": prop.id,
        "designation": prop.designation,
        "municipality": prop.municipality,
        "county": prop.county,
        "area_sqm": prop.area_sqm,
        "assessed_value_sek": prop.assessed_value_sek,
        "property_type": prop.property_type,
        "owner_name": prop.owner_name,
        "owner_org_number": prop.owner_org_number,
        "address": prop.address,
        "postal_code": prop.postal_code,
        "city": prop.city,
        "building_year": prop.building_year,
        "living_area_sqm": prop.living_area_sqm,
        "zoning": prop.zoning,
        "metadata_json": prop.metadata_json or {},
        "created_at": prop.created_at.isoformat() if prop.created_at else None,
        "updated_at": prop.updated_at.isoformat() if prop.updated_at else None,
    }

    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": properties,
    }


@router.get("/", response_model=PropertyCollection)
async def list_properties(
    municipality: str | None = Query(None, description="Filter by municipality"),
    property_type: str | None = Query(None, description="Filter by property type"),
    min_value: float | None = Query(None, description="Minimum assessed value (SEK)"),
    max_value: float | None = Query(None, description="Maximum assessed value (SEK)"),
    bbox: str | None = Query(
        None, description="Bounding box: west,south,east,north"
    ),
    db: Session = Depends(get_db),
):
    """List properties as a GeoJSON FeatureCollection."""
    query = db.query(Property)

    if municipality:
        query = query.filter(Property.municipality == municipality)
    if property_type:
        query = query.filter(Property.property_type == property_type)
    if min_value is not None:
        query = query.filter(Property.assessed_value_sek >= min_value)
    if max_value is not None:
        query = query.filter(Property.assessed_value_sek <= max_value)
    if bbox:
        try:
            west, south, east, north = [float(c) for c in bbox.split(",")]
            envelope = ST_MakeEnvelope(west, south, east, north, 4326)
            query = query.filter(ST_Within(Property.geometry, envelope))
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail="Invalid bbox format. Use: west,south,east,north",
            )

    properties = query.all()
    features = [model_to_feature(p) for p in properties]

    return {"type": "FeatureCollection", "features": features}


@router.get("/search", response_model=PropertyCollection)
async def search_properties(
    q: str = Query(..., description="Search query"),
    db: Session = Depends(get_db),
):
    """Search properties by designation, address, or owner name (case-insensitive)."""
    search_pattern = f"%{q}%"
    properties = (
        db.query(Property)
        .filter(
            or_(
                Property.designation.ilike(search_pattern),
                Property.address.ilike(search_pattern),
                Property.owner_name.ilike(search_pattern),
            )
        )
        .all()
    )

    features = [model_to_feature(p) for p in properties]
    return {"type": "FeatureCollection", "features": features}


@router.get("/{property_id}", response_model=PropertyFeature)
async def get_property(
    property_id: int,
    db: Session = Depends(get_db),
):
    """Get a single property as a GeoJSON Feature."""
    prop = db.query(Property).filter(Property.id == property_id).first()

    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    return model_to_feature(prop)


@router.post("/", response_model=PropertyFeature, status_code=201)
async def create_property(
    data: PropertyCreate,
    db: Session = Depends(get_db),
):
    """Create a new property."""
    prop = Property(
        designation=data.designation,
        municipality=data.municipality,
        county=data.county,
        area_sqm=data.area_sqm,
        assessed_value_sek=data.assessed_value_sek,
        property_type=data.property_type,
        owner_name=data.owner_name,
        owner_org_number=data.owner_org_number,
        address=data.address,
        postal_code=data.postal_code,
        city=data.city,
        building_year=data.building_year,
        living_area_sqm=data.living_area_sqm,
        zoning=data.zoning,
        metadata_json=data.metadata_json,
    )

    # Convert GeoJSON geometry to WKT for PostGIS
    if data.geometry:
        from shapely.geometry import shape as shapely_shape

        geom = shapely_shape(data.geometry)
        prop.geometry = geom.wkt

    db.add(prop)
    db.commit()
    db.refresh(prop)

    return model_to_feature(prop)
