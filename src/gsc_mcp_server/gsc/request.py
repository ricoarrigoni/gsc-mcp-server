"""Build the searchAnalytics.query body.

The critical detail: Search Console silently ignores a top-level `filters`
field. Filters must be wrapped in `dimensionFilterGroups` or the query runs
unfiltered and looks fine. Callers pass a flat list; this module wraps it.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..analysis.periods import resolve_range
from ..constants import (
    DEFAULT_ROW_LIMIT,
    DIMENSIONS,
    EXCLUSIVE_DIMENSIONS,
    FILTER_OPERATORS,
    MAX_ROW_LIMIT,
    DateRange,
    Dimension,
    SearchType,
)


class RequestValidationError(ValueError):
    """Rejected before the API call, with a message naming the fix."""


def validate_dimensions(dimensions: list[str] | None) -> list[str]:
    dims = list(dimensions or ["query"])
    if not dims:
        raise RequestValidationError("dimensions must not be empty.")
    unknown = [d for d in dims if d not in DIMENSIONS]
    if unknown:
        raise RequestValidationError(
            f"Unknown dimension(s) {unknown}. Valid: {list(DIMENSIONS)}."
        )
    exclusive = EXCLUSIVE_DIMENSIONS.intersection(dims)
    if exclusive and len(dims) > 1:
        name = next(iter(exclusive))
        raise RequestValidationError(
            f"{name} must be the only dimension when used. Search Console "
            "rejects it combined with any other dimension."
        )
    if len(dims) != len(set(dims)):
        raise RequestValidationError("dimensions contains duplicates.")
    return dims


def validate_filters(filters: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in filters or []:
        dimension = raw.get("dimension")
        operator = raw.get("operator", "equals")
        expression = raw.get("expression")
        if dimension not in DIMENSIONS:
            raise RequestValidationError(
                f"Filter dimension {dimension!r} is not valid. "
                f"Valid: {list(DIMENSIONS)}."
            )
        if operator not in FILTER_OPERATORS:
            raise RequestValidationError(
                f"Filter operator {operator!r} is not valid. "
                f"Valid: {list(FILTER_OPERATORS)}."
            )
        if not expression:
            raise RequestValidationError("Filter expression must not be empty.")
        out.append(
            {
                "dimension": dimension,
                "operator": operator,
                "expression": expression,
            }
        )
    return out


def build_search_analytics_request(
    *,
    dimensions: list[Dimension] | None = None,
    date_range: DateRange | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    filters: list[dict[str, Any]] | None = None,
    row_limit: int | None = None,
    start_row: int | None = None,
    search_type: SearchType = "web",
    data_state: str = "all",
    today: date | None = None,
) -> dict[str, Any]:
    dims = validate_dimensions(dimensions)
    resolved_start, resolved_end = resolve_range(
        date_range=date_range,
        start_date=start_date,
        end_date=end_date,
        today=today,
    )
    limit = max(1, min(row_limit or DEFAULT_ROW_LIMIT, MAX_ROW_LIMIT))

    body: dict[str, Any] = {
        "startDate": resolved_start,
        "endDate": resolved_end,
        "dimensions": dims,
        "rowLimit": limit,
        "type": search_type,
        "dataState": data_state,
    }
    if start_row:
        body["startRow"] = start_row

    wrapped = validate_filters(filters)
    if wrapped:
        # Must be dimensionFilterGroups. A top-level "filters" key is ignored.
        body["dimensionFilterGroups"] = [
            {"groupType": "and", "filters": wrapped}
        ]
    return body
