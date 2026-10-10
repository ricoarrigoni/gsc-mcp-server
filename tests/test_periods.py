from datetime import date

import pytest

from gsc_mcp_server.analysis.periods import (
    previous_period,
    resolve_range,
    retention_floor,
    subtract_months,
)

TODAY = date(2026, 10, 10)


def test_convenience_range_ends_before_the_data_lag():
    start, end = resolve_range(date_range="last_28_days", today=TODAY)
    assert end == "2026-10-07"
    assert start == "2026-09-10"


@pytest.mark.parametrize(("name", "days"), [("last_7_days", 7), ("last_28_days", 28)])
def test_day_ranges_cover_exactly_that_many_days_inclusive(name, days):
    start, end = resolve_range(date_range=name, today=TODAY)
    assert (date.fromisoformat(end) - date.fromisoformat(start)).days + 1 == days


def test_month_ranges_do_not_overlap_the_month_before():
    start, end = resolve_range(date_range="last_3_months", today=TODAY)
    assert (start, end) == ("2026-07-08", "2026-10-07")


def test_default_range_is_last_28_days():
    assert resolve_range(today=TODAY) == resolve_range(
        date_range="last_28_days", today=TODAY
    )


def test_explicit_start_older_than_16_months_is_clamped_up():
    floor = retention_floor(TODAY).isoformat()
    start, end = resolve_range(
        start_date="2020-01-01", end_date="2026-10-01", today=TODAY
    )
    assert start == floor
    assert end == "2026-10-01"


def test_half_specified_range_is_rejected():
    with pytest.raises(ValueError, match="both startDate and endDate"):
        resolve_range(start_date="2026-09-01", today=TODAY)
    with pytest.raises(ValueError, match="both startDate and endDate"):
        resolve_range(end_date="2026-09-30", today=TODAY)


def test_end_before_start_is_rejected():
    with pytest.raises(ValueError, match="before startDate"):
        resolve_range(start_date="2026-09-30", end_date="2026-09-01", today=TODAY)


def test_month_subtraction_clamps_short_months():
    assert subtract_months(date(2026, 3, 31), 1) == date(2026, 2, 28)
    assert subtract_months(date(2026, 1, 15), 1) == date(2025, 12, 15)
    assert subtract_months(date(2026, 1, 31), 13) == date(2024, 12, 31)


def test_previous_period_is_equal_length_and_adjacent():
    prev_start, prev_end = previous_period("2026-09-10", "2026-10-07")
    assert prev_end == "2026-09-09"
    assert prev_start == "2026-08-13"
    assert (date(2026, 9, 9) - date(2026, 8, 13)).days + 1 == 28
