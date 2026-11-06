from datetime import UTC, date, datetime

import pytest

from app.api.v1.admin_analytics import reporting_bounds
from app.services.exam_access import AccessError


@pytest.mark.parametrize(
    ("period", "day"),
    [
        ("daily", "2026-11-05"),
        ("weekly", "2026-11-01"),
        ("monthly", "2026-10-31"),
        ("yearly", "2025-12-31"),
    ],
)
def test_kigali_reporting_bounds(period, day):
    timestamp = datetime(2026, 11, 5, 22, tzinfo=UTC)
    start, end = reporting_bounds(timestamp, period)
    assert start.isoformat() == day + "T22:00:00+00:00"
    assert end.isoformat() == "2026-11-06T22:00:00+00:00"


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 11, 5), None),
        (date(2026, 11, 6), date(2026, 11, 5)),
        (date(2024, 11, 5), date(2026, 11, 5)),
        (date(2026, 11, 5), date(2026, 12, 5)),
    ],
)
def test_invalid_range(start, end):
    with pytest.raises(AccessError) as error:
        reporting_bounds(datetime(2026, 11, 5, tzinfo=UTC), "daily", start, end)
    assert error.value.code == "INVALID_REPORTING_RANGE"
