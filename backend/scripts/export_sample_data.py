"""Exportera seed-fixturerna som demodata till frontenden.

Skriver frontend/src/data/sampleData.json med exakt samma form som
API:ts svar (FeatureCollections för fastigheter, projekt och
påverkanszoner). Demo-läget kan därmed aldrig glida ifrån kontraktet.

    uv run python -m scripts.export_sample_data
"""

import json
import math
from datetime import date
from pathlib import Path
from typing import Any

from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.ops import transform as shapely_transform

from app.schemas import (
    DesoAreaCollection,
    DesoAreaFeature,
    DesoAreaProps,
    DetailPlanCollection,
    DetailPlanFeature,
    DetailPlanProps,
    ImpactZoneCollection,
    ImpactZoneFeature,
    ImpactZoneProps,
    InfrastructureProjectCollection,
    InfrastructureProjectFeature,
    InfrastructureProjectProps,
    PropertyCollection,
    PropertyFeature,
    PropertyProps,
    ProximityScoreFeature,
    ProximityScoreProps,
    ProximityScoresCollection,
    ScoreContribution,
)
from app.seed_data import DESO_AREAS, DETAIL_PLANS, INFRASTRUCTURE_PROJECTS, PROPERTIES
from app.services import scoring

OUTPUT_PATH = Path(__file__).parents[2] / "frontend" / "src" / "data" / "sampleData.json"

M_PER_DEG_LAT = 111_320.0

# Fast referensdatum så att exporten är deterministisk — CI regenererar
# och diffar filen, och poängmodellens tidsfaktor får inte glida med
# dagens datum. Uppdatera medvetet vid behov (och committa om filen).
REFERENCE_DATE = date(2026, 8, 5)


def _buffer_wgs84(geometry: dict[str, Any], meters: float) -> dict[str, Any]:
    """Buffra en WGS84-geometri i meter via lokal ekvirektangulär skalning.

    Fullt tillräckligt för demodata — riktiga zoner beräknas av PostGIS
    över geography i backend.
    """
    geom = shape(geometry)
    lat = geom.centroid.y
    m_per_deg_lng = M_PER_DEG_LAT * math.cos(math.radians(lat))

    to_meters = shapely_transform(lambda x, y: (x * m_per_deg_lng, y * M_PER_DEG_LAT), geom)
    buffered = to_meters.buffer(meters)
    back = shapely_transform(lambda x, y: (x / m_per_deg_lng, y / M_PER_DEG_LAT), buffered)
    return json.loads(json.dumps(mapping(back)))


def _to_multipolygon(geometry: dict[str, Any]) -> dict[str, Any]:
    geom = shape(geometry)
    if isinstance(geom, Polygon):
        geom = MultiPolygon([geom])
    return json.loads(json.dumps(mapping(geom)))


def _distance_m(geometry_a: dict[str, Any], geometry_b: dict[str, Any]) -> float:
    """Approximativt avstånd i meter via lokal ekvirektangulär skalning.

    Riktiga avstånd beräknas av PostGIS — det här räcker för demodata.
    """
    geom_a = shape(geometry_a)
    geom_b = shape(geometry_b)
    lat = (geom_a.centroid.y + geom_b.centroid.y) / 2
    m_per_deg_lng = M_PER_DEG_LAT * math.cos(math.radians(lat))

    def to_meters(geom):
        return shapely_transform(lambda x, y: (x * m_per_deg_lng, y * M_PER_DEG_LAT), geom)

    return to_meters(geom_a).distance(to_meters(geom_b))


def _build_proximity_scores() -> ProximityScoresCollection:
    """Demo-poäng med SAMMA poängmodell som API:t (app.services.scoring)."""
    scored = []
    for prop_index, prop in enumerate(PROPERTIES, start=1):
        if prop.geometry is None:
            continue
        contributions = []
        for project_index, project in enumerate(INFRASTRUCTURE_PROJECTS, start=1):
            if project.geometry is None:
                continue
            distance = _distance_m(prop.geometry, project.geometry)
            if distance > scoring.DEFAULT_MAX_DISTANCE_M:
                continue
            points = scoring.project_points(
                scoring.ScoredProject(
                    project_type=project.project_type,
                    status=project.status,
                    budget_sek=project.budget_sek,
                    end_date=project.end_date,
                    distance_m=distance,
                ),
                max_distance_m=scoring.DEFAULT_MAX_DISTANCE_M,
                today=REFERENCE_DATE,
            )
            contributions.append(
                ScoreContribution(
                    project_id=project_index,
                    name=project.name,
                    project_type=project.project_type,
                    status=project.status,
                    distance_m=round(distance, 1),
                    points=points,
                )
            )
        if contributions:
            contributions.sort(key=lambda c: c.points, reverse=True)
            scored.append((prop_index, prop, contributions))

    scored.sort(key=lambda entry: scoring.total_score([c.points for c in entry[2]]), reverse=True)

    features = [
        ProximityScoreFeature(
            geometry=_to_multipolygon(prop.geometry) if prop.geometry else None,
            properties=ProximityScoreProps(
                id=prop_index,
                **prop.model_dump(exclude={"geometry"}),
                score=scoring.total_score([c.points for c in contributions]),
                rank=rank,
                contributions=contributions,
            ),
        )
        for rank, (prop_index, prop, contributions) in enumerate(scored, start=1)
    ]

    return ProximityScoresCollection(
        features=features,
        numberMatched=len(features),
        numberReturned=len(features),
        max_distance_m=scoring.DEFAULT_MAX_DISTANCE_M,
    )


def _area_km2(geometry: dict[str, Any]) -> float:
    """Approximativ yta i km² via lokal ekvirektangulär skalning.

    Riktiga ytor beräknas av PostGIS (geography) — det här räcker för
    demodata och speglar samma fält i API-svaret.
    """
    geom = shape(geometry)
    lat = geom.centroid.y
    m_per_deg_lng = M_PER_DEG_LAT * math.cos(math.radians(lat))
    to_meters = shapely_transform(lambda x, y: (x * m_per_deg_lng, y * M_PER_DEG_LAT), geom)
    return round(to_meters.area / 1_000_000, 3)


def _build_detail_plans() -> DetailPlanCollection:
    features = [
        DetailPlanFeature(
            geometry=_to_multipolygon(item.geometry) if item.geometry else None,
            properties=DetailPlanProps(
                id=index,
                **item.model_dump(exclude={"geometry"}),
            ),
        )
        for index, item in enumerate(DETAIL_PLANS, start=1)
    ]
    return DetailPlanCollection(
        features=features, numberMatched=len(features), numberReturned=len(features)
    )


def _build_deso_areas() -> DesoAreaCollection:
    features = []
    for index, item in enumerate(DESO_AREAS, start=1):
        area_km2 = _area_km2(item.geometry) if item.geometry else None
        density = None
        if area_km2 and item.population is not None:
            density = round(item.population / area_km2, 1)
        features.append(
            DesoAreaFeature(
                geometry=_to_multipolygon(item.geometry) if item.geometry else None,
                properties=DesoAreaProps(
                    id=index,
                    **item.model_dump(exclude={"geometry"}),
                    area_km2=area_km2,
                    population_density=density,
                ),
            )
        )
    return DesoAreaCollection(
        features=features, numberMatched=len(features), numberReturned=len(features)
    )


def build_sample_data() -> dict[str, Any]:
    property_features = [
        PropertyFeature(
            geometry=_to_multipolygon(item.geometry) if item.geometry else None,
            properties=PropertyProps(
                id=index,
                **item.model_dump(exclude={"geometry"}),
            ),
        )
        for index, item in enumerate(PROPERTIES, start=1)
    ]

    project_features = [
        InfrastructureProjectFeature(
            geometry=item.geometry,
            properties=InfrastructureProjectProps(
                id=index,
                **item.model_dump(exclude={"geometry"}),
            ),
        )
        for index, item in enumerate(INFRASTRUCTURE_PROJECTS, start=1)
    ]

    zone_features = [
        ImpactZoneFeature(
            geometry=_buffer_wgs84(item.geometry, item.impact_radius_m),
            properties=ImpactZoneProps(
                project_id=index,
                name=item.name,
                project_type=item.project_type,
                status=item.status,
                start_date=item.start_date,
                end_date=item.end_date,
                impact_radius_m=item.impact_radius_m,
            ),
        )
        for index, item in enumerate(INFRASTRUCTURE_PROJECTS, start=1)
        if item.geometry is not None
    ]

    return {
        "properties": PropertyCollection(
            features=property_features,
            numberMatched=len(property_features),
            numberReturned=len(property_features),
        ).model_dump(mode="json"),
        "infrastructureProjects": InfrastructureProjectCollection(
            features=project_features,
            numberMatched=len(project_features),
            numberReturned=len(project_features),
        ).model_dump(mode="json"),
        "impactZones": ImpactZoneCollection(features=zone_features).model_dump(mode="json"),
        "proximityScores": _build_proximity_scores().model_dump(mode="json"),
        "detailPlans": _build_detail_plans().model_dump(mode="json"),
        "desoAreas": _build_deso_areas().model_dump(mode="json"),
    }


def main() -> None:
    data = build_sample_data()
    OUTPUT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Skrev {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
