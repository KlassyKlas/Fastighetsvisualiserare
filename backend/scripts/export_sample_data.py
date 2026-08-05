"""Exportera seed-fixturerna som demodata till frontenden.

Skriver frontend/src/data/sampleData.json med exakt samma form som
API:ts svar (FeatureCollections för fastigheter, projekt och
påverkanszoner). Demo-läget kan därmed aldrig glida ifrån kontraktet.

    uv run python -m scripts.export_sample_data
"""

import json
import math
from pathlib import Path
from typing import Any

from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.ops import transform as shapely_transform

from app.schemas import (
    ImpactZoneCollection,
    ImpactZoneFeature,
    ImpactZoneProps,
    InfrastructureProjectCollection,
    InfrastructureProjectFeature,
    InfrastructureProjectProps,
    PropertyCollection,
    PropertyFeature,
    PropertyProps,
)
from app.seed_data import INFRASTRUCTURE_PROJECTS, PROPERTIES

OUTPUT_PATH = Path(__file__).parents[2] / "frontend" / "src" / "data" / "sampleData.json"

M_PER_DEG_LAT = 111_320.0


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
    }


def main() -> None:
    data = build_sample_data()
    OUTPUT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Skrev {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
