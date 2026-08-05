"""Konvertering från ORM-rader (+ ST_AsGeoJSON-resultat) till API-scheman.

Geometrier serialiseras av PostGIS (ST_AsGeoJSON) direkt i frågan —
ingen shapely-rundresa per rad.
"""

from datetime import date

from app.models import DesoArea, DetailPlan, InfrastructureProject, Property
from app.schemas import (
    DesoAreaFeature,
    DesoAreaProps,
    DetailPlanFeature,
    DetailPlanProps,
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


def detail_plan_feature(plan: DetailPlan, geojson: str | None) -> DetailPlanFeature:
    return DetailPlanFeature(
        geometry=parse_geojson_column(geojson),
        properties=DetailPlanProps.model_validate(plan),
    )


def deso_area_feature(
    area: DesoArea, geojson: str | None, area_m2: float | None
) -> DesoAreaFeature:
    """DeSO-feature med yta och befolkningstäthet härledda ur PostGIS-arean."""
    props = DesoAreaProps.model_validate(area)
    if area_m2 and area_m2 > 0:
        props.area_km2 = round(area_m2 / 1_000_000, 3)
        if area.population is not None:
            props.population_density = round(area.population / props.area_km2, 1)
    return DesoAreaFeature(geometry=parse_geojson_column(geojson), properties=props)


def impact_zone_feature(
    project_id: int,
    name: str,
    project_type: str | None,
    status: str | None,
    start_date: date | None,
    end_date: date | None,
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
            start_date=start_date,
            end_date=end_date,
            impact_radius_m=impact_radius_m,
        ),
    )
