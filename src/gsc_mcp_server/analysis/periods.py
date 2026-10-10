"""Date range resolution.

Two traps live here:

  1. Search Console data trails by 2 to 3 days, so a convenience range that
     ends today returns a misleading tail. Convenience ranges end
     DATA_LAG_DAYS back.
  2. Nothing older than 16 months exists. An explicit start date older than
     that is clamped up, not passed through.

A half-specified explicit range is rejected by the caller, not silently
turned into a default window.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..constants import DATA_LAG_DAYS, RETENTION_MONTHS, DateRange

_RANGE_DAYS: dict[str, int] = {"last_7_days": 7, "last_28_days": 28}
_RANGE_MONTHS: dict[str, int] = {
    "last_3_months": 3,
    "last_6_months": 6,
    "last_12_months": 12,
    "last_16_months": 16,
}


def subtract_months(value: date, months: int) -> date:
    """Subtract calendar months, clamping the day to the target month length."""
    total = value.year * 12 + (value.month - 1) - months
    year, month = divmod(total, 12)
    month += 1
    # Day 1 of the following month minus one day gives the last valid day.
    if month == 12:
        last_day = (date(year + 1, 1, 1) - timedelta(days=1)).day
    else:
        last_day = (date(year, month + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(value.day, last_day))


def retention_floor(today: date) -> date:
    return subtract_months(today, RETENTION_MONTHS)


def resolve_range(
    *,
    date_range: DateRange | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    today: date | None = None,
) -> tuple[str, str]:
    """Return (startDate, endDate) as YYYY-MM-DD strings.

    An explicit start/end pair wins. Its start is clamped to the 16-month
    floor. Otherwise the named range is resolved backwards from
    today - DATA_LAG_DAYS.
    """
    today = today or date.today()
    floor = retention_floor(today)

    if start_date and end_date:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        if start < floor:
            start = floor
        if end < start:
            raise ValueError("endDate is before startDate.")
        return start.isoformat(), end.isoformat()

    if bool(start_date) != bool(end_date):
        raise ValueError(
            "Provide both startDate and endDate, or neither. A half-specified "
            "range would silently fall back to a default window."
        )

    name = date_range or "last_28_days"
    end = today - timedelta(days=DATA_LAG_DAYS)
    if name in _RANGE_DAYS:
        start = end - timedelta(days=_RANGE_DAYS[name])
    elif name in _RANGE_MONTHS:
        start = subtract_months(end, _RANGE_MONTHS[name])
    else:
        raise ValueError(f"Unknown dateRange {name!r}.")

    if start < floor:
        start = floor
    return start.isoformat(), end.isoformat()


def previous_period(start_date: str, end_date: str) -> tuple[str, str]:
    """The equal-length window immediately before the one given.

    Used by compare_periods so the model never does this arithmetic itself.
    """
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    span = (end - start).days
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span)
    return prev_start.isoformat(), prev_end.isoformat()
