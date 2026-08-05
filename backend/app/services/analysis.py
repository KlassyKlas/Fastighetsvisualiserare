"""Spatial analys: kopplingen mellan fastigheter och infrastrukturprojekt.

Detta är appens kärnfråga — vilka fastigheter berörs av vilka projekt —
och den besvaras i databasen med ST_DWithin/ST_Distance över geography
(meter), inte med klientsidig buffring i grader.
"""

from datetime import date

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import ProjectStatus, ProjectType
from app.models import InfrastructureProject, Property
from app.schemas import (
    AffectedPropertiesCollection,
    AffectedPropertyFeature,
    AffectedPropertyProps,
    AffectingProject,
    InfrastructureProjectProps,
    NearbyProject,
    NearbyProjectsResponse,
    PropertyProps,
    ProximityScoreFeature,
    ProximityScoreProps,
    ProximityScoresCollection,
    ScoreContribution,
)
from app.services import scoring
from app.services.geo import parse_geojson_column


# OBS: Geography(srid=4326) — utan srid renderar GeoAlchemy2 typmoden
# geography(GEOMETRY,-1), som inte matchar de funktionella indexen
# (idx_*_geometry_geog) och därmed gör dem verkningslösa.
def _prop_geog():
    return cast(Property.geometry, Geography(srid=4326))


def _proj_geog():
    return cast(InfrastructureProject.geometry, Geography(srid=4326))


async def nearby_projects(
    session: AsyncSession, property_id: int, max_distance_m: float
) -> NearbyProjectsResponse | None:
    """Projekt inom max_distance_m meter från en fastighet, närmast först."""
    exists = await session.scalar(select(Property.id).where(Property.id == property_id))
    if exists is None:
        return None

    distance = func.ST_Distance(_prop_geog(), _proj_geog()).label("distance_m")

    rows = await session.execute(
        select(InfrastructureProject, distance)
        .select_from(Property)
        .join(
            InfrastructureProject,
            func.ST_DWithin(_prop_geog(), _proj_geog(), max_distance_m),
        )
        .where(
            Property.id == property_id,
            Property.geometry.is_not(None),
            InfrastructureProject.geometry.is_not(None),
        )
        .order_by(distance)
    )

    projects = [
        NearbyProject(
            project=InfrastructureProjectProps.model_validate(project),
            distance_m=round(dist, 1),
            within_impact_radius=dist <= project.impact_radius_m,
        )
        for project, dist in rows.all()
    ]

    return NearbyProjectsResponse(
        property_id=property_id, max_distance_m=max_distance_m, projects=projects
    )


async def affected_properties(
    session: AsyncSession,
    *,
    statuses: list[ProjectStatus] | None = None,
    project_types: list[ProjectType] | None = None,
    limit: int = 500,
) -> AffectedPropertiesCollection:
    """Fastigheter som ligger inom påverkansradien för (filtrerade) projekt,
    med avstånd till varje påverkande projekt."""
    distance = func.ST_Distance(_prop_geog(), _proj_geog()).label("distance_m")

    conditions = [
        Property.geometry.is_not(None),
        InfrastructureProject.geometry.is_not(None),
    ]
    if statuses:
        conditions.append(InfrastructureProject.status.in_(statuses))
    if project_types:
        conditions.append(InfrastructureProject.project_type.in_(project_types))

    rows = await session.execute(
        select(
            Property,
            func.ST_AsGeoJSON(Property.geometry),
            InfrastructureProject.id,
            InfrastructureProject.name,
            InfrastructureProject.project_type,
            InfrastructureProject.status,
            distance,
        )
        .select_from(Property)
        .join(
            InfrastructureProject,
            func.ST_DWithin(_prop_geog(), _proj_geog(), InfrastructureProject.impact_radius_m),
        )
        .where(*conditions)
        .order_by(Property.id, distance)
    )

    features_by_id: dict[int, AffectedPropertyFeature] = {}
    seen_ids: set[int] = set()

    for prop, geojson, project_id, name, project_type, status, dist in rows.all():
        seen_ids.add(prop.id)
        feature = features_by_id.get(prop.id)
        if feature is None:
            if len(features_by_id) >= limit:
                continue
            feature = AffectedPropertyFeature(
                geometry=parse_geojson_column(geojson),
                properties=AffectedPropertyProps(
                    **PropertyProps.model_validate(prop).model_dump(),
                    affecting_projects=[],
                ),
            )
            features_by_id[prop.id] = feature
        feature.properties.affecting_projects.append(
            AffectingProject(
                project_id=project_id,
                name=name,
                project_type=project_type,
                status=status,
                distance_m=round(dist, 1),
            )
        )

    return AffectedPropertiesCollection(
        features=list(features_by_id.values()),
        numberMatched=len(seen_ids),
        numberReturned=len(features_by_id),
    )


async def proximity_scores(
    session: AsyncSession,
    *,
    statuses: list[ProjectStatus] | None = None,
    project_types: list[ProjectType] | None = None,
    max_distance_m: float = scoring.DEFAULT_MAX_DISTANCE_M,
    limit: int = 500,
    today: date | None = None,
) -> ProximityScoresCollection:
    """Närhetspoäng: rankade fastigheter utifrån omgivande projekt.

    Avstånden beräknas i PostGIS (geography, meter); själva poängmodellen
    ligger i app.services.scoring och redovisas bidrag för bidrag.
    """
    if today is None:
        today = date.today()

    distance = func.ST_Distance(_prop_geog(), _proj_geog()).label("distance_m")

    conditions = [
        Property.geometry.is_not(None),
        InfrastructureProject.geometry.is_not(None),
    ]
    if statuses:
        conditions.append(InfrastructureProject.status.in_(statuses))
    if project_types:
        conditions.append(InfrastructureProject.project_type.in_(project_types))

    rows = await session.execute(
        select(
            Property,
            func.ST_AsGeoJSON(Property.geometry),
            InfrastructureProject,
            distance,
        )
        .select_from(Property)
        .join(
            InfrastructureProject,
            func.ST_DWithin(_prop_geog(), _proj_geog(), max_distance_m),
        )
        .where(*conditions)
        .order_by(Property.id)
    )

    scored: dict[int, dict] = {}
    for prop, geojson, project, dist in rows.all():
        entry = scored.setdefault(prop.id, {"prop": prop, "geojson": geojson, "contributions": []})
        points = scoring.project_points(
            scoring.ScoredProject(
                project_type=project.project_type,
                status=project.status,
                budget_sek=project.budget_sek,
                end_date=project.end_date,
                distance_m=dist,
            ),
            max_distance_m=max_distance_m,
            today=today,
        )
        entry["contributions"].append(
            ScoreContribution(
                project_id=project.id,
                name=project.name,
                project_type=project.project_type,
                status=project.status,
                distance_m=round(dist, 1),
                points=points,
            )
        )

    ranked = sorted(
        scored.values(),
        key=lambda entry: scoring.total_score([c.points for c in entry["contributions"]]),
        reverse=True,
    )

    features = []
    for rank, entry in enumerate(ranked[:limit], start=1):
        contributions = sorted(entry["contributions"], key=lambda c: c.points, reverse=True)
        features.append(
            ProximityScoreFeature(
                geometry=parse_geojson_column(entry["geojson"]),
                properties=ProximityScoreProps(
                    **PropertyProps.model_validate(entry["prop"]).model_dump(),
                    score=scoring.total_score([c.points for c in contributions]),
                    rank=rank,
                    contributions=contributions,
                ),
            )
        )

    return ProximityScoresCollection(
        features=features,
        numberMatched=len(scored),
        numberReturned=len(features),
        max_distance_m=max_distance_m,
    )
