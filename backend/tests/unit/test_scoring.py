"""Poängmodellen är ren aritmetik — här låses dess beteende fast."""

from datetime import date

from app.services.scoring import (
    DEFAULT_MAX_DISTANCE_M,
    ScoredProject,
    budget_factor,
    distance_factor,
    project_points,
    time_factor,
    total_score,
)

TODAY = date(2026, 8, 5)


class TestDistanceFactor:
    def test_at_project_is_full(self):
        assert distance_factor(0, 5000) == 1.0

    def test_at_radius_is_zero(self):
        assert distance_factor(5000, 5000) == 0.0

    def test_halfway_is_half(self):
        assert distance_factor(2500, 5000) == 0.5

    def test_beyond_radius_clamped_to_zero(self):
        assert distance_factor(9000, 5000) == 0.0

    def test_negative_distance_clamped_to_one(self):
        assert distance_factor(-2500, 5000) == 1.0


class TestBudgetFactor:
    def test_unknown_budget_is_neutral(self):
        assert budget_factor(None) == 0.5
        assert budget_factor(0) == 0.5

    def test_hundred_billion_is_max(self):
        assert budget_factor(100_000_000_000) == 1.0

    def test_one_billion(self):
        assert 0.8 < budget_factor(1_000_000_000) < 0.85

    def test_tiny_budget_has_floor(self):
        assert budget_factor(100) == 0.2


class TestTimeFactor:
    def test_unknown_end_is_neutral(self):
        assert time_factor(None, TODAY) == 0.85

    def test_past_end_is_dampened(self):
        assert time_factor(date(2020, 1, 1), TODAY) == 0.75

    def test_near_term_is_full(self):
        assert time_factor(date(2028, 1, 1), TODAY) == 1.0

    def test_medium_term(self):
        assert time_factor(date(2033, 1, 1), TODAY) == 0.85

    def test_distant_future_is_dampened(self):
        assert time_factor(date(2045, 1, 1), TODAY) == 0.7


class TestProjectPoints:
    def test_planned_railway_beats_finished_roadwork(self):
        railway = ScoredProject(
            project_type="järnväg",
            status="planerad",
            budget_sek=90_000_000_000,
            end_date=date(2029, 1, 1),
            distance_m=1000,
        )
        roadwork = ScoredProject(
            project_type="väg",
            status="avslutad",
            budget_sek=1_000_000_000,
            end_date=date(2015, 1, 1),
            distance_m=1000,
        )
        assert project_points(
            railway, max_distance_m=DEFAULT_MAX_DISTANCE_M, today=TODAY
        ) > 3 * project_points(roadwork, max_distance_m=DEFAULT_MAX_DISTANCE_M, today=TODAY)

    def test_unknown_type_and_status_get_defaults(self):
        project = ScoredProject(
            project_type=None,
            status=None,
            budget_sek=None,
            end_date=None,
            distance_m=0,
        )
        # 100 × 0.2 (typ) × 0.5 (status) × 1.0 (avstånd) × 0.5 (budget) × 0.85 (tid)
        assert project_points(project, max_distance_m=5000, today=TODAY) == 4.2

    def test_out_of_range_project_gives_zero(self):
        project = ScoredProject(
            project_type="järnväg",
            status="planerad",
            budget_sek=1_000_000_000,
            end_date=None,
            distance_m=6000,
        )
        assert project_points(project, max_distance_m=5000, today=TODAY) == 0.0


def test_total_score_is_rounded_sum():
    assert total_score([10.5, 20.25]) == 30.8
    assert total_score([]) == 0.0


def test_sample_export_scores_use_same_model():
    from scripts.export_sample_data import build_sample_data

    scores = build_sample_data()["proximityScores"]
    assert scores["numberReturned"] >= 1
    features = scores["features"]
    # Sorterade med rank 1 först och fallande poäng
    ranks = [f["properties"]["rank"] for f in features]
    assert ranks == list(range(1, len(features) + 1))
    score_values = [f["properties"]["score"] for f in features]
    assert score_values == sorted(score_values, reverse=True)
    # Varje poäng är summan av sina bidrag
    for feature in features:
        props = feature["properties"]
        assert props["score"] == round(sum(c["points"] for c in props["contributions"]), 1)
