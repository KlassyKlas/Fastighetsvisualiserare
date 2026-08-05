"""Konvertering från ORM-rader (+ ST_AsGeoJSON-resultat) till API-scheman.

Geometrier serialiseras av PostGIS (ST_AsGeoJSON) direkt i frågan —
ingen shapely-rundresa per rad.
"""

from app.models import InfrastructureProject, Property
from app.schemas import (
    ImpactZoneFeature,
    ImpactZoneProps,
    InfrastructureProjectFeature,
    InfrastructureProjectProps,
    PropertyFeature,
    PropertyProps,
)
from app.services.geo import parse_geojson_column


def property_feature(prop: Property, geojson: str | None) -> PropertyFeature:
    return PropertyFeature(
        geometry=parse_geojson_column(geojson),
        properties=PropertyProps.model_validate(prop),
    )


def project_feature(
    project: InfrastructureProject, geojson: str | None
) -> InfrastructureProjectFeature:
    return InfrastructureProjectFeature(
        geometry=parse_geojson_column(geojson),
        properties=InfrastructureProjectProps.model_validate(project),
    )


def impact_zone_feature(
    project_id: int,
    name: str,
    project_type: str | None,
    status: str | None,
    impact_radius_m: float,
    geojson: str | None,
) -> ImpactZoneFeature:
    return ImpactZoneFeature(
        geometry=parse_geojson_column(geojson),
        properties=ImpactZoneProps(
            project_id=project_id,
            name=name,
            project_type=project_type,
            status=status,
            impact_radius_m=impact_radius_m,
        ),
    )
