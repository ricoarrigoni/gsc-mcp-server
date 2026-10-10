"""Search Analytics tools: get_data_freshness, query_performance,
top_queries, top_pages, compare_periods, export_query.

All of them build the request through gsc/request.py, so the trap guards
(dimensionFilterGroups wrapping, exclusive searchAppearance, half-specified
ranges, the 1,000-row inline cap) apply to every one.
"""

from __future__ import annotations

import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, Literal

from mcp.types import CallToolResult
from pydantic import Field

from ..analysis.compare import comparison_response, comparison_window
from ..analysis.export import write_rows_csv
from ..analysis.periods import retention_floor
from ..analysis.shaping import performance_response, redact_rows, redaction_note
from ..constants import (
    DATA_LAG_DAYS,
    EXPORT_DEFAULT_ROWS,
    EXPORT_MAX_ROWS,
    MAX_ROW_LIMIT,
    DataState,
    Dimension,
)
from ..gsc.freshness import Freshness
from ..gsc.pagination import iter_pages
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
    freshness = Freshness(context.client)

    @server.tool(
        name="get_data_freshness",
        title="Check data freshness",
        description=(
            "The latest date with final (complete) data for a property, and "
            "the latest date with any provisional data, checked against the "
            "last 10 days. Use it before reporting 'yesterday' or the most "
            "recent days: Search Console usually trails by 2 to 3 days. "
            "Read-only."
        ),
        annotations=READ_ONLY,
    )
    def get_data_freshness(siteUrl: SiteUrl) -> CallToolResult:
        if not context.config.allows(siteUrl):
            return not_allowed(siteUrl)

        def body():
            info = freshness.check(siteUrl)
            final, latest = info["latestFinalDate"], info["latestDate"]
            if final:
                text = (
                    f"{siteUrl} | final data through {final} "
                    f"({info['finalLagDays']} days ago)"
                    + (f", provisional through {latest}" if latest else "")
                )
            else:
                text = (
                    f"{siteUrl} | no final web data in the last 10 days "
                    f"(since {info['lookbackStart']}). The property may be new "
                    "or have no traffic."
                )
            return result(text, {"ok": True, "siteUrl": siteUrl, **info}), {
                "startDate": info["lookbackStart"],
                "endDate": info["today"],
            }

        return run_tool("get_data_freshness", siteUrl, body)

    def anchored_today(site_url: str) -> date | None:
        """A 'today' for resolve_range that ends named windows on final data.

        resolve_range ends a named window DATA_LAG_DAYS before `today`, so
        shifting today to latest-final + lag ends it on the latest final day.
        Explicit dates are left alone. Falls back to the fixed lag when the
        property has no recent final data.
        """
        latest = freshness.latest_final(site_url)
        if latest is None:
            return None
        return latest + timedelta(days=DATA_LAG_DAYS)

    def run_query(
        site_url: str, request: dict[str, Any], top_n: int | None = None
    ) -> tuple[CallToolResult, dict[str, Any]]:
        rows = context.client.query_search_analytics(site_url, request)
        text, structured = performance_response(
            site_url=site_url,
            request=request,
            rows=rows,
            redact_pii=context.config.redact_pii,
            top_n=top_n,
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
                f"Top {noun} ranked by clicks, then impressions, default the "
                "last 28 days and 50 rows. A shortcut for query_performance; "
                "use that for other groupings. Read-only."
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
                    # Fetch the full inline page so the re-rank by
                    # impressions sees the rows Google sorted past rowLimit.
                    row_limit=MAX_ROW_LIMIT,
                    search_type=searchType,
                )
                return run_query(siteUrl, request, top_n=rowLimit)

            return run_tool(tool, siteUrl, body)

    top("top_queries", "query", "Top search queries", "search queries")
    top("top_pages", "page", "Top pages", "pages")

    @server.tool(
        name="compare_periods",
        title="Compare two periods",
        description=(
            "Diff performance between a window and the one before it (or the "
            "same dates a year earlier), computed server-side on final data "
            "only. A named dateRange ends on the latest final day (see "
            "get_data_freshness). Returns totals "
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
                # Partial recent days would read as a drop.
                "data_state": "final",
            }
            explicit = bool(startDate or endDate)
            current = build_search_analytics_request(
                date_range=dateRange,
                start_date=startDate,
                end_date=endDate,
                today=None if explicit else anchored_today(siteUrl),
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
            query = context.client.query_search_analytics
            current_rows = query(siteUrl, current)
            previous_rows = query(siteUrl, previous)
            current_totals = previous_totals = None
            if dims:
                # Window totals from a no-dimension query, so they mean the
                # same thing whichever dimension is diffed.
                current_totals = query(siteUrl, {**current, "dimensions": []})
                previous_totals = query(siteUrl, {**previous, "dimensions": []})
            text, structured = comparison_response(
                current_totals=current_totals,
                previous_totals=previous_totals,
                site_url=siteUrl,
                current_request=current,
                previous_request=previous,
                current_rows=current_rows,
                previous_rows=previous_rows,
                limit=limit,
                redact_pii=context.config.redact_pii,
            )
            return result(text, structured), {
                "startDate": previous["startDate"],
                "endDate": current["endDate"],
                "rows": len(current_rows) + len(previous_rows),
            }

        return run_tool("compare_periods", siteUrl, body)

    @server.tool(
        name="export_query",
        title="Export performance data to CSV",
        description=(
            "Write a large Search Analytics pull to a CSV file on this "
            "machine and return the file path and row count, never the rows. "
            f"Pages through the API up to maxRows (at most {EXPORT_MAX_ROWS:,}). "
            "Use this instead of query_performance when more than 1,000 rows "
            "are needed. Read-only against Search Console."
        ),
        annotations=READ_ONLY,
    )
    def export_query(
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
        maxRows: Annotated[
            int,
            Field(ge=1, le=EXPORT_MAX_ROWS, description="Stop after this many rows."),
        ] = EXPORT_DEFAULT_ROWS,
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
                search_type=searchType,
                data_state=dataState,
            )
            dims = request["dimensions"]
            stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            name = (
                f"gsc-export-{stamp}-{'-'.join(dims) or 'totals'}-"
                f"{secrets.token_hex(3)}.csv"
            )
            path = context.config.exports_path / name
            fetched = dropped = 0

            def pages():
                nonlocal fetched, dropped
                for page in iter_pages(
                    context.client, siteUrl, request, max_rows=maxRows
                ):
                    fetched += len(page)
                    if context.config.redact_pii:
                        page, n = redact_rows(page, dims)
                        dropped += n
                    yield page

            count = write_rows_csv(path, dims, pages())
            truncated = fetched >= maxRows
            structured = {
                "ok": True,
                "siteUrl": siteUrl,
                "path": str(path),
                "rowCount": count,
                "columns": [*dims, "clicks", "impressions", "ctr", "position"],
                "startDate": request["startDate"],
                "endDate": request["endDate"],
                "searchType": searchType,
                "truncated": truncated,
            }
            if context.config.redact_pii:
                structured["redactedRows"] = dropped
            text = (
                f"Wrote {count:,} row{'' if count == 1 else 's'} to {path}\n"
                f"{siteUrl} | {'+'.join(dims) or 'totals'} | "
                f"{request['startDate']} to {request['endDate']}"
                + (
                    f"\nStopped at maxRows={maxRows:,}; more rows may exist."
                    if truncated
                    else ""
                )
                + (f"\n{redaction_note(dropped)}" if dropped else "")
            )
            return result(text, structured), _log_fields(request, count)

        return run_tool("export_query", siteUrl, body)
