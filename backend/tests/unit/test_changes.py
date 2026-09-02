"""Enhetstester för den rena logiken i "Nytt sedan senast".

SQL-frågorna körs i PostGIS och täcks av integrationstesterna — här
testas tidsnormaliseringen, den delade händelseklassificeringen och
limit-fördelningen.
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.domain import WatchEventKind
from app.services import watches
from app.services.changes import classify_event, ensure_utc, take_with_overflow

SEEN = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


def test_ensure_utc_treats_naive_as_utc():
    result = ensure_utc(datetime(2026, 9, 1, 12, 0))
    assert result.tzinfo is UTC
    assert result == datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def test_ensure_utc_converts_other_offsets_to_utc():
    stockholm_summer = datetime(2026, 9, 1, 14, 0, tzinfo=timezone(timedelta(hours=2)))
    result = ensure_utc(stockholm_summer)
    assert result.tzinfo is UTC
    assert result == datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def test_ensure_utc_keeps_utc_value():
    value = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    assert ensure_utc(value) == value
    assert ensure_utc(value).tzinfo is UTC


@pytest.mark.parametrize(
    "value",
    [
        datetime(1, 1, 1, 0, 0, tzinfo=timezone(timedelta(hours=5))),
        datetime(9999, 12, 31, 23, 0, tzinfo=timezone(-timedelta(hours=5))),
    ],
)
def test_ensure_utc_rejects_values_outside_datetime_range(value):
    """Giltig ISO-text vars UTC-form lämnar år 1–9999 ska ge ValueError (→ 422), inte 500."""
    with pytest.raises(ValueError, match="tidsrymd"):
        ensure_utc(value)


def test_classify_event_is_shared_with_watches():
    """Bevakningarna använder samma regel — flytten får inte lämna en kopia kvar."""
    assert watches.classify_event is classify_event


def test_classify_event_rules():
    before = SEEN - timedelta(days=1)
    after = SEEN + timedelta(days=1)
    assert classify_event(after, after, SEEN) == WatchEventKind.NYTT
    assert classify_event(before, after, SEEN) == WatchEventKind.ANDRAT
    assert classify_event(before, before, SEEN) is None
    assert classify_event(None, None, SEEN) is None


def test_take_with_overflow_reports_extra_row():
    rows = ["a", "b", "c"]
    assert take_with_overflow(rows, 2) == (["a", "b"], True)
    assert take_with_overflow(rows, 3) == (["a", "b", "c"], False)
    assert take_with_overflow(rows, 5) == (["a", "b", "c"], False)


def test_take_with_overflow_zero_budget_still_detects_rows():
    """När projekten fyllt hela limit hämtas ändå en plan — bara för truncated."""
    assert take_with_overflow(["x"], 0) == ([], True)
    assert take_with_overflow([], 0) == ([], False)
