import json
from pathlib import Path

from gsc_mcp_server.analysis.shaping import compact_row, performance_response

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_position_is_omitted_when_google_omits_it():
    rows = load("search_analytics_discover.json")["rows"]
    out = [compact_row(r) for r in rows]
    assert all("position" not in r for r in out)


def test_discover_response_explains_the_missing_position():
    rows = load("search_analytics_discover.json")["rows"]
    request = {
        "startDate": "2026-09-01",
        "endDate": "2026-09-02",
        "dimensions": ["date"],
        "rowLimit": 1000,
        "type": "discover",
        "dataState": "all",
    }
    text, structured = performance_response(
        site_url="sc-domain:example.com", request=request, rows=rows
    )
    assert "not report position" in " ".join(structured["notes"])
    assert "discover" in text


def test_has_more_is_true_when_rows_hit_the_requested_limit():
    rows = load("search_analytics_query.json")["rows"]
    request = {
        "startDate": "2026-09-01",
        "endDate": "2026-09-28",
        "dimensions": ["query"],
        "rowLimit": 3,
        "startRow": 0,
        "type": "web",
        "dataState": "all",
    }
    _, structured = performance_response(
        site_url="sc-domain:example.com", request=request, rows=rows
    )
    assert structured["hasMore"] is True
    assert structured["nextStartRow"] == 3


def test_has_more_is_false_when_fewer_rows_than_the_limit():
    rows = load("search_analytics_query.json")["rows"]
    request = {
        "startDate": "2026-09-01",
        "endDate": "2026-09-28",
        "dimensions": ["query"],
        "rowLimit": 1000,
        "type": "web",
        "dataState": "all",
    }
    _, structured = performance_response(
        site_url="sc-domain:example.com", request=request, rows=rows
    )
    assert structured["hasMore"] is False
    assert "nextStartRow" not in structured


def _notes(dimensions):
    request = {
        "startDate": "2026-09-01",
        "endDate": "2026-09-28",
        "dimensions": dimensions,
        "rowLimit": 1000,
        "type": "web",
        "dataState": "all",
    }
    _, structured = performance_response(
        site_url="sc-domain:example.com", request=request, rows=[]
    )
    return " ".join(structured["notes"])


def test_query_responses_carry_the_anonymised_query_caveat():
    assert "anonymised" in _notes(["query"])
    assert "anonymised" in _notes(["page", "query"])


def test_caveats_match_the_grouping():
    assert "drops some rows" in _notes(["page"])
    assert "anonymised" not in _notes(["page"])
    assert _notes(["date"]) == ""
    assert _notes(["country", "device"]) == ""
    assert _notes([]) == "Property totals include anonymised queries."
