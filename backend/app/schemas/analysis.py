from typing import Literal

from pydantic import BaseModel, Field

from app.domain import ProjectStatus, ProjectType
from app.schemas.infrastructure import InfrastructureProjectProps
from app.schemas.property import PropertyProps


class NearbyProject(BaseModel):
    """Ett infrastrukturprojekt i närheten av en fastighet."""

    project: InfrastructureProjectProps
    distance_m: float = Field(description="Avstånd i meter från fastigheten till projektet")
    within_impact_radius: bool = Field(
        description="Om fastigheten ligger inom projektets påverkansradie"
    )


class NearbyProjectsResponse(BaseModel):
    property_id: int
    max_distance_m: float
    projects: list[NearbyProject] = Field(default_factory=list)


class AffectingProject(BaseModel):
    """Kompakt referens till ett projekt som påverkar en fastighet."""

    project_id: int
    name: str
    project_type: ProjectType | None = None
    status: ProjectStatus | None = None
    distance_m: float


class AffectedPropertyProps(PropertyProps):
    affecting_projects: list[AffectingProject] = Field(default_factory=list)


class AffectedPropertyFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: dict | None = None
    properties: AffectedPropertyProps


class AffectedPropertiesCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[AffectedPropertyFeature] = Field(default_factory=list)
    numberMatched: int
    numberReturned: int


class ScoreContribution(BaseModel):
    """Ett enskilt projekts bidrag till en fastighets närhetspoäng."""

    project_id: int
    name: str
    project_type: ProjectType | None = None
    status: ProjectStatus | None = None
    distance_m: float
    points: float


class ProximityScoreProps(PropertyProps):
    score: float = Field(description="Summan av alla projektbidrag — högre är bättre läge")
    rank: int = Field(description="1 = högst poäng i svaret")
    contributions: list[ScoreContribution] = Field(
        default_factory=list, description="Bidragen bakom poängen, största först"
    )


class ProximityScoreFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: dict | None = None
    properties: ProximityScoreProps


class ProximityScoresCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[ProximityScoreFeature] = Field(
        default_factory=list, description="Sorterade efter poäng, högst först"
    )
    numberMatched: int
    numberReturned: int
    max_distance_m: float = Field(description="Sökradien som poängen beräknats med")
