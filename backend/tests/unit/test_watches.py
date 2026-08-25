"""Enhetstester för händelseklassificeringen i bevakningstjänsten.

Själva intersect-frågorna körs i PostGIS och täcks av
integrationstesterna — här testas den rena tidslogiken.
"""

from datetime import UTC, datetime

from app.domain import WatchEventKind
from app.services.watches import classify_event

SEEN = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
BEFORE = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
AFTER = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


def test_created_after_seen_is_new():
    assert classify_event(AFTER, AFTER, SEEN) == WatchEventKind.NYTT


def test_only_updated_after_seen_is_changed():
    assert classify_event(BEFORE, AFTER, SEEN) == WatchEventKind.ANDRAT


def test_untouched_since_seen_is_no_event():
    assert classify_event(BEFORE, BEFORE, SEEN) is None


def test_new_wins_over_changed():
    """Ett objekt som både skapats och uppdaterats efter seen_at är nytt."""
    later = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
    assert classify_event(AFTER, later, SEEN) == WatchEventKind.NYTT


def test_missing_timestamps_give_no_event():
    assert classify_event(None, None, SEEN) is None


def test_missing_created_at_falls_back_to_updated_at():
    assert classify_event(None, AFTER, SEEN) == WatchEventKind.ANDRAT
    assert classify_event(None, BEFORE, SEEN) is None
