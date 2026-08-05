"""Närhetspoäng: rankning av fastigheter mot omgivande infrastrukturprojekt.

Modellen är medvetet enkel och helt transparent — varje fastighets poäng
är summan av bidrag från projekt inom sökradien, och varje bidrag
redovisas för sig i API-svaret så att rankningen alltid går att förklara.

    bidrag = 100 × typvikt × statusvikt × avståndsfaktor × budgetfaktor × tidsfaktor

- Typvikt: spårbunden infrastruktur väger tyngst — järnvägar och
  kollektivtrafik driver fastighetsvärden mer än vägarbeten.
- Statusvikt: planerade projekt väger tyngst; det är innan spaden går i
  marken som informationsövertaget finns. Avslutade projekt är redan
  inprisade.
- Avståndsfaktor: linjärt avtagande från 1.0 vid projektet till 0 vid
  sökradien.
- Budgetfaktor: logaritmisk — ett 90-miljardersprojekt ska väga tyngre än
  ett vägarbete, men inte 1000× tyngre.
- Tidsfaktor: färdigställande inom ett par år väger tyngst; mycket
  avlägsna eller redan passerade sluttider dämpas.

Modulen är ren (inga databasanrop, ingen klocka) — samma funktioner
används av analystjänsten (PostGIS-avstånd) och demodata-exporten
(approximativa avstånd), så demo-läget kan aldrig visa en annan modell
än den riktiga.
"""

import math
from dataclasses import dataclass
from datetime import date

from app.domain import ProjectStatus, ProjectType

DEFAULT_MAX_DISTANCE_M = 5000.0

TYPE_WEIGHTS: dict[ProjectType, float] = {
    ProjectType.JARNVAG: 1.0,
    ProjectType.KOLLEKTIVTRAFIK: 0.9,
    ProjectType.TUNNEL: 0.7,
    ProjectType.BRO: 0.6,
    ProjectType.VAG: 0.5,
    ProjectType.CYKELVAG: 0.3,
    ProjectType.OVRIGT: 0.2,
}
DEFAULT_TYPE_WEIGHT = 0.2

STATUS_WEIGHTS: dict[ProjectStatus, float] = {
    ProjectStatus.PLANERAD: 1.0,
    ProjectStatus.PAGAENDE: 0.7,
    ProjectStatus.AVSLUTAD: 0.3,
}
DEFAULT_STATUS_WEIGHT = 0.5


@dataclass(frozen=True)
class ScoredProject:
    """Det poängmodellen behöver veta om ett projekt nära en fastighet."""

    project_type: str | None
    status: str | None
    budget_sek: int | None
    end_date: date | None
    distance_m: float


def distance_factor(distance_m: float, max_distance_m: float) -> float:
    """Linjärt avtagande 1.0 → 0.0 över sökradien."""
    if max_distance_m <= 0:
        return 0.0
    return max(0.0, 1.0 - distance_m / max_distance_m)


def budget_factor(budget_sek: int | None) -> float:
    """Logaritmisk budgetvikt: 100 mdkr → 1.0, 1 mdkr → ~0.82, golv 0.2.

    Okänd budget ger neutralt 0.5 — hellre försiktig än att gissa högt.
    """
    if budget_sek is None or budget_sek <= 0:
        return 0.5
    return min(1.0, max(0.2, math.log10(budget_sek) / 11.0))


def time_factor(end_date: date | None, today: date) -> float:
    """Färdigställande inom ~3 år väger tyngst.

    Okänd sluttid → 0.85 (neutralt). Passerad sluttid → 0.75 (effekten
    börjar vara inprisad; statusvikten dämpar redan avslutade projekt).
    """
    if end_date is None:
        return 0.85
    years_until = (end_date - today).days / 365.25
    if years_until <= 0:
        return 0.75
    if years_until <= 3:
        return 1.0
    if years_until <= 10:
        return 0.85
    return 0.7


def project_points(project: ScoredProject, *, max_distance_m: float, today: date) -> float:
    """Ett enskilt projekts bidrag till en fastighets närhetspoäng."""
    type_weight = DEFAULT_TYPE_WEIGHT
    if project.project_type is not None:
        try:
            type_weight = TYPE_WEIGHTS.get(ProjectType(project.project_type), DEFAULT_TYPE_WEIGHT)
        except ValueError:
            type_weight = DEFAULT_TYPE_WEIGHT

    status_weight = DEFAULT_STATUS_WEIGHT
    if project.status is not None:
        try:
            status_weight = STATUS_WEIGHTS.get(ProjectStatus(project.status), DEFAULT_STATUS_WEIGHT)
        except ValueError:
            status_weight = DEFAULT_STATUS_WEIGHT

    points = (
        100.0
        * type_weight
        * status_weight
        * distance_factor(project.distance_m, max_distance_m)
        * budget_factor(project.budget_sek)
        * time_factor(project.end_date, today)
    )
    return round(points, 1)


def total_score(contributions: list[float]) -> float:
    """En fastighets poäng är summan av alla projektbidrag."""
    return round(sum(contributions), 1)
