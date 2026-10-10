from datetime import date, timedelta
from urllib.parse import unquote

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from gsc_mcp_server.analysis.compare import diff_rows
from gsc_mcp_server.analysis.periods import subtract_months
from tests.conftest import load_fixture

SITE = "sc-domain:example.com"


async def test_query_performance_returns_table_and_structured_rows(harness):
    harness.queue(load_fixture("search_analytics_query.json"))
    server = harness.server()

    out = await harness.call(server, "query_performance", siteUrl=SITE)

    assert "blue widgets" in out.content[0].text
    assert out.structured_content["ok"] is True
    assert out.structured_content["rowCount"] == 3
    assert out.structured_content["rows"][0]["position"] == 4.2


async def test_site_url_reaches_google_verbatim(harness):
    server = harness.server()
    await harness.call(server, "query_performance", siteUrl="https://example.com/")
    assert "/sites/https%3A%2F%2Fexample.com%2F/" in str(harness.requests[0].url)
    assert unquote(str(harness.requests[0].url)).count("https://example.com/") == 1


async def test_filters_are_wrapped_in_dimension_filter_groups(harness):
    server = harness.server()
    await harness.call(
        server,
        "query_performance",
        siteUrl=SITE,
        filters=[{"dimension": "page", "operator": "contains", "expression": "/a"}],
    )
    body = harness.bodies()[0]
    assert "filters" not in body
    assert body["dimensionFilterGroups"][0]["filters"][0]["expression"] == "/a"


async def test_search_appearance_with_another_dimension_is_rejected(harness):
    server = harness.server()
    out = await harness.call(
        server,
        "query_performance",
        siteUrl=SITE,
        dimensions=["searchAppearance", "query"],
    )
    assert out.structured_content == {
        "ok": False,
        "reason": "invalid_request",
        "message": out.structured_content["message"],
    }
    assert harness.requests == []


async def test_half_specified_range_is_rejected_not_defaulted(harness):
    server = harness.server()
    out = await harness.call(
        server, "query_performance", siteUrl=SITE, startDate="2026-09-01"
    )
    assert out.structured_content["reason"] == "invalid_request"
    assert harness.requests == []


async def test_empty_dimensions_queries_property_totals(harness):
    harness.queue({"rows": [{"clicks": 10, "impressions": 100, "ctr": 0.1}]})
    server = harness.server()
    out = await harness.call(server, "query_performance", siteUrl=SITE, dimensions=[])
    assert harness.bodies()[0]["dimensions"] == []
    assert "totals" in out.content[0].text


async def test_discover_rows_have_no_position(harness):
    harness.queue(load_fixture("search_analytics_discover.json"))
    server = harness.server()
    out = await harness.call(
        server,
        "query_performance",
        siteUrl=SITE,
        dimensions=["date"],
        searchType="discover",
    )
    assert all("position" not in r for r in out.structured_content["rows"])


async def test_row_limit_above_the_inline_cap_is_refused_by_schema(harness):
    server = harness.server()
    with pytest.raises(ToolError, match="rowLimit"):
        await harness.call(server, "query_performance", siteUrl=SITE, rowLimit=5000)
    assert harness.requests == []


async def test_property_outside_the_allowlist_is_refused(harness):
    server = harness.server(property_allowlist=("https://example.com/",))
    out = await harness.call(server, "top_queries", siteUrl=SITE)
    assert out.structured_content["reason"] == "property_not_allowed"
    assert harness.requests == []


async def test_api_error_is_mapped_to_ok_false(harness):
    harness.queue(httpx.Response(404, text="not found"))
    server = harness.server()
    out = await harness.call(server, "top_pages", siteUrl=SITE)
    assert out.structured_content["ok"] is False
    assert "sc-domain" in out.structured_content["message"]


async def test_top_queries_and_top_pages_group_and_default_to_fifty(harness):
    server = harness.server()
    await harness.call(server, "top_queries", siteUrl=SITE)
    await harness.call(server, "top_pages", siteUrl=SITE)
    queries, pages = harness.bodies()
    assert queries["dimensions"] == ["query"]
    assert pages["dimensions"] == ["page"]
    # The full inline page is fetched, then cut to the default of 50.
    assert queries["rowLimit"] == pages["rowLimit"] == 1000


async def test_top_queries_breaks_click_ties_by_impressions(harness):
    harness.queue(
        {
            "rows": [
                {"keys": ["a"], "clicks": 0, "impressions": 3, "ctr": 0},
                {"keys": ["b"], "clicks": 0, "impressions": 90, "ctr": 0},
                {"keys": ["c"], "clicks": 2, "impressions": 5, "ctr": 0.4},
            ]
        }
    )
    server = harness.server()
    out = await harness.call(server, "top_queries", siteUrl=SITE, rowLimit=2)
    s = out.structured_content
    assert [r["keys"] for r in s["rows"]] == [["c"], ["b"]]
    assert s["hasMore"] is True
    assert "nextStartRow" not in s


async def test_compare_periods_queries_adjacent_windows_and_diffs(harness):
    harness.queue(
        {"rows": [{"keys": ["a"], "clicks": 10, "impressions": 100, "ctr": 0.1}]},
        {"rows": [{"keys": ["a"], "clicks": 4, "impressions": 80, "ctr": 0.05}]},
        {"rows": [{"clicks": 15, "impressions": 130, "ctr": 0.11}]},
        {"rows": [{"clicks": 6, "impressions": 95, "ctr": 0.06}]},
    )
    server = harness.server()
    out = await harness.call(
        server,
        "compare_periods",
        siteUrl=SITE,
        startDate="2026-09-08",
        endDate="2026-09-14",
    )
    current, previous, current_totals, previous_totals = harness.bodies()
    assert (previous["startDate"], previous["endDate"]) == ("2026-09-01", "2026-09-07")
    assert current["rowLimit"] == previous["rowLimit"] == 1000
    assert current_totals["dimensions"] == previous_totals["dimensions"] == []
    assert current_totals["startDate"] == current["startDate"]
    assert previous_totals["startDate"] == previous["startDate"]
    row = out.structured_content["rows"][0]
    assert row["delta"]["clicks"] == 6
    # Totals are the property totals, not the sum of the rows.
    assert out.structured_content["current"]["clicks"] == 15
    assert out.structured_content["previous"]["clicks"] == 6
    assert out.structured_content["totalsScope"] == "property"


async def test_compare_previous_year_beyond_retention_is_rejected(harness):
    server = harness.server()
    out = await harness.call(
        server,
        "compare_periods",
        siteUrl=SITE,
        dateRange="last_6_months",
        compareTo="previous_year",
    )
    assert out.structured_content["reason"] == "invalid_request"
    assert "retention" in out.structured_content["message"]
    # Only the freshness lookup reached Google, no comparison query.
    assert [b["dimensions"] for b in harness.bodies()] == [["date"]]


async def test_compare_previous_year_within_retention_uses_same_dates(harness):
    server = harness.server()
    end = date.today() - timedelta(days=10)
    start = end - timedelta(days=6)
    await harness.call(
        server,
        "compare_periods",
        siteUrl=SITE,
        startDate=start.isoformat(),
        endDate=end.isoformat(),
        compareTo="previous_year",
        dimension=None,
    )
    # dimension null: the rows are the totals, no extra totals queries.
    current, previous = harness.bodies()
    assert current["dimensions"] == previous["dimensions"] == []
    assert previous["startDate"] == subtract_months(start, 12).isoformat()
    assert previous["endDate"] == subtract_months(end, 12).isoformat()


def test_diff_marks_new_and_lost_and_keeps_position_absent():
    current = [
        {"keys": ["kept"], "clicks": 5, "impressions": 50, "ctr": 0.1, "position": 3},
        {"keys": ["new"], "clicks": 9, "impressions": 90, "ctr": 0.1},
    ]
    previous = [
        {"keys": ["kept"], "clicks": 7, "impressions": 60, "ctr": 0.11, "position": 4},
        {"keys": ["lost"], "clicks": 2, "impressions": 20, "ctr": 0.1},
    ]
    rows = {tuple(r["keys"]): r for r in diff_rows(current, previous)}
    assert rows[("new",)]["status"] == "new"
    assert rows[("lost",)]["status"] == "lost"
    assert rows[("kept",)]["delta"]["position"] == -1.0
    assert "position" not in rows[("new",)]["delta"]
    assert diff_rows(current, previous)[0]["keys"] == ["new"]


async def test_get_data_freshness_tool(harness):
    final = (date.today() - timedelta(days=3)).isoformat()
    latest = (date.today() - timedelta(days=1)).isoformat()
    harness.queue(
        {"rows": [{"keys": [final], "clicks": 1, "impressions": 1, "ctr": 1}]},
        {"rows": [{"keys": [latest], "clicks": 1, "impressions": 1, "ctr": 1}]},
    )
    server = harness.server()
    out = await harness.call(server, "get_data_freshness", siteUrl=SITE)
    assert out.structured_content["latestFinalDate"] == final
    assert out.structured_content["finalLagDays"] == 3
    assert f"final data through {final}" in out.content[0].text


async def test_compare_named_range_ends_on_the_latest_final_day(harness):
    final = date.today() - timedelta(days=5)
    harness.queue(
        {
            "rows": [
                {"keys": [final.isoformat()], "clicks": 1, "impressions": 1, "ctr": 1}
            ]
        },
    )
    server = harness.server()
    await harness.call(server, "compare_periods", siteUrl=SITE, dateRange="last_7_days")
    _, current, previous, *_ = harness.bodies()
    assert current["endDate"] == final.isoformat()
    assert current["dataState"] == previous["dataState"] == "final"


async def test_compare_explicit_dates_skip_the_freshness_lookup(harness):
    server = harness.server()
    await harness.call(
        server,
        "compare_periods",
        siteUrl=SITE,
        startDate="2026-09-08",
        endDate="2026-09-14",
    )
    # Rows and totals for each window; no freshness lookup.
    assert len(harness.requests) == 4
    assert all(b["dimensions"] != ["date"] for b in harness.bodies())
