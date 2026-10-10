"""Search Analytics tools: query_performance, top_queries, top_pages,
compare_periods.

All of them build the request through gsc/request.py, so the trap guards
(dimensionFilterGroups wrapping, exclusive searchAppearance, half-specified
ranges, the 1,000-row inline cap) apply to every one.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from mcp.types import CallToolResult
from pydantic import Field

from ..analysis.compare import comparison_response, comparison_window
from ..analysis.periods import retention_floor
from ..analysis.shaping import performance_response
from ..constants import MAX_ROW_LIMIT, DataState, Dimension
from ..gsc.request import build_search_analytics_request
from ._common import (
    READ_ONLY,
    DateRangeArg,
    EndDate,
    FiltersArg,
    SearchTypeArg,
    SiteUrl,
    StartDate,
    filter_dicts,
    not_allowed,
    result,
    run_tool,
)

InlineRowLimit = Annotated[
    int,
    Field(
        ge=1,
        le=MAX_ROW_LIMIT,
        description=(
            f"Rows to return, at most {MAX_ROW_LIMIT}. Use export_query for "
            "larger pulls."
        ),
    ),
]
DataStateArg = Annotated[
    DataState,
    Field(
        description=(
            "'all' includes the most recent, still-changing days; 'final' "
            "only finalised data."
        )
    ),
]


def _log_fields(request: dict[str, Any], rows: int) -> dict[str, Any]:
    return {
        "startDate": request["startDate"],
        "endDate": request["endDate"],
        "rows": rows,
    }


def register(server, context) -> None:
    def run_query(
        site_url: str, request: dict[str, Any]
    ) -> tuple[CallToolResult, dict[str, Any]]:
        rows = context.client.query_search_analytics(site_url, request)
        text, structured = performance_response(
            site_url=site_url, request=request, rows=rows
        )
        return result(text, structured), _log_fields(request, len(rows))

    @server.tool(
        name="query_performance",
        title="Query search performance",
        description=(
            "Search Console performance data (clicks, impressions, CTR, "
            "position) grouped by any dimensions, with filters. Pass "
            "dimensions=[] for property totals, which are the only figures "
            "that include anonymised queries. searchAppearance must be the "
            "only dimension when used. Returns a table plus structured rows; "
            "when hasMore is true, call again with startRow=nextStartRow. "
            "Read-only."
        ),
        annotations=READ_ONLY,
    )
    def query_performance(
        siteUrl: SiteUrl,
        dimensions: Annotated[
            list[Dimension] | None,
            Field(description="Group by these. Default ['query']."),
        ] = None,
        dateRange: DateRangeArg = None,
        startDate: StartDate = None,
        endDate: EndDate = None,
        filters: FiltersArg = None,
        searchType: SearchTypeArg = "web",
        dataState: DataStateArg = "all",
        rowLimit: InlineRowLimit = MAX_ROW_LIMIT,
        startRow: Annotated[int, Field(ge=0)] = 0,
    ) -> CallToolResult:
        if not context.config.allows(siteUrl):
            return not_allowed(siteUrl)

        def body():
            request = build_search_analytics_request(
                dimensions=dimensions,
                date_range=dateRange,
                start_date=startDate,
                end_date=endDate,
                filters=filter_dicts(filters),
                row_limit=rowLimit,
                start_row=startRow,
                search_type=searchType,
                data_state=dataState,
            )
            return run_query(siteUrl, request)

        return run_tool("query_performance", siteUrl, body)

    def top(tool: str, dimension: Dimension, title: str, noun: str) -> None:
        @server.tool(
            name=tool,
            title=title,
            description=(
                f"Top {noun} by clicks, default the last 28 days and 50 rows. "
                "A shortcut for query_performance; use that for other "
                "groupings. Read-only."
            ),
            annotations=READ_ONLY,
        )
        def top_tool(
            siteUrl: SiteUrl,
            dateRange: DateRangeArg = None,
            startDate: StartDate = None,
            endDate: EndDate = None,
            filters: FiltersArg = None,
            searchType: SearchTypeArg = "web",
            rowLimit: InlineRowLimit = 50,
        ) -> CallToolResult:
            if not context.config.allows(siteUrl):
                return not_allowed(siteUrl)

            def body():
                request = build_search_analytics_request(
                    dimensions=[dimension],
                    date_range=dateRange,
                    start_date=startDate,
                    end_date=endDate,
                    filters=filter_dicts(filters),
                    row_limit=rowLimit,
                    search_type=searchType,
                )
                return run_query(siteUrl, request)

            return run_tool(tool, siteUrl, body)

    top("top_queries", "query", "Top search queries", "search queries")
    top("top_pages", "page", "Top pages", "pages")

    @server.tool(
        name="compare_periods",
        title="Compare two periods",
        description=(
            "Diff performance between a window and the one before it (or the "
            "same dates a year earlier), computed server-side. Returns totals "
            "for both windows and per-key deltas sorted by absolute click "
            "change, with each key marked new, lost or changed. dimension=null "
            "compares property totals only. Read-only."
        ),
        annotations=READ_ONLY,
    )
    def compare_periods(
        siteUrl: SiteUrl,
        dimension: Annotated[
            Literal["query", "page", "country", "device", "searchAppearance"] | None,
            Field(description="Key to diff on. null for property totals only."),
        ] = "query",
        dateRange: DateRangeArg = None,
        startDate: StartDate = None,
        endDate: EndDate = None,
        compareTo: Annotated[
            Literal["previous_period", "previous_year"],
            Field(
                description=(
                    "previous_period: the equal-length window just before. "
                    "previous_year: the same dates 12 months earlier."
                )
            ),
        ] = "previous_period",
        filters: FiltersArg = None,
        searchType: SearchTypeArg = "web",
        limit: Annotated[
            int,
            Field(ge=1, le=MAX_ROW_LIMIT, description="Rows of deltas to return."),
        ] = 25,
    ) -> CallToolResult:
        if not context.config.allows(siteUrl):
            return not_allowed(siteUrl)

        def body():
            dims: list[Dimension] = [dimension] if dimension else []
            common: dict[str, Any] = {
                "dimensions": dims,
                "filters": filter_dicts(filters),
                "row_limit": MAX_ROW_LIMIT,
                "search_type": searchType,
            }
            current = build_search_analytics_request(
                date_range=dateRange,
                start_date=startDate,
                end_date=endDate,
                **common,
            )
            prev_start, prev_end = comparison_window(
                current["startDate"], current["endDate"], compareTo
            )
            floor = retention_floor(date.today())
            if date.fromisoformat(prev_start) < floor:
                raise ValueError(
                    f"The comparison window would start {prev_start}, before "
                    f"the 16-month retention floor {floor.isoformat()}. Choose "
                    "a shorter or more recent window."
                )
            previous = build_search_analytics_request(
                start_date=prev_start, end_date=prev_end, **common
            )
            current_rows = context.client.query_search_analytics(siteUrl, current)
            previous_rows = context.client.query_search_analytics(siteUrl, previous)
            text, structured = comparison_response(
                site_url=siteUrl,
                current_request=current,
                previous_request=previous,
                current_rows=current_rows,
                previous_rows=previous_rows,
                limit=limit,
            )
            return result(text, structured), {
                "startDate": previous["startDate"],
                "endDate": current["endDate"],
                "rows": len(current_rows) + len(previous_rows),
            }

        return run_tool("compare_periods", siteUrl, body)
