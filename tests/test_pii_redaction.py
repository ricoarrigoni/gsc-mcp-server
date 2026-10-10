import csv

import pytest

from gsc_mcp_server.analysis.shaping import looks_like_pii, performance_response

SITE = "sc-domain:example.com"


@pytest.mark.parametrize(
    "text",
    [
        "jane.doe@example.com",
        "call +44 20 7946 0958",
        "(555) 123-4567 ext",
        "account 123456789",
    ],
)
def test_personal_looking_queries_are_flagged(text):
    assert looks_like_pii(text)


@pytest.mark.parametrize(
    "text",
    ["blue widgets", "tax year 2025-2026", "iphone 15 pro", "route 66", "@widgets"],
)
def test_ordinary_queries_are_kept(text):
    assert not looks_like_pii(text)


def rows(*queries):
    return [
        {"keys": [q], "clicks": 1, "impressions": 1, "ctr": 1.0, "position": 1}
        for q in queries
    ]


REQUEST = {
    "startDate": "2026-09-01",
    "endDate": "2026-09-28",
    "dimensions": ["query"],
    "rowLimit": 2,
    "type": "web",
}


def test_redaction_drops_rows_but_keeps_pagination_honest():
    _, s = performance_response(
        site_url=SITE,
        request=REQUEST,
        rows=rows("blue widgets", "jane@example.com"),
        redact_pii=True,
    )
    assert [r["keys"] for r in s["rows"]] == [["blue widgets"]]
    assert s["redactedRows"] == 1
    assert s["hasMore"] is True
    assert s["nextStartRow"] == 2
    assert any("GSC_REDACT_PII" in n for n in s["notes"])


def test_redaction_is_off_by_default():
    _, s = performance_response(
        site_url=SITE, request=REQUEST, rows=rows("jane@example.com")
    )
    assert s["rowCount"] == 1
    assert "redactedRows" not in s


def test_redaction_ignores_non_query_dimensions():
    request = {**REQUEST, "dimensions": ["page"]}
    _, s = performance_response(
        site_url=SITE,
        request=request,
        rows=rows("https://example.com/p/123456789"),
        redact_pii=True,
    )
    assert s["rowCount"] == 1


async def test_tools_honour_redact_pii(harness, tmp_path):
    harness.queue(
        {"rows": rows("blue widgets", "jane@example.com")},
        {"rows": rows("blue widgets", "jane@example.com")},
        {"rows": rows("jane@example.com")},
        {"rows": rows("blue widgets", "jane@example.com")},
    )
    server = harness.server(redact_pii=True, export_dir=tmp_path)

    q = await harness.call(server, "top_queries", siteUrl=SITE)
    c = await harness.call(
        server,
        "compare_periods",
        siteUrl=SITE,
        startDate="2026-09-08",
        endDate="2026-09-14",
    )
    e = await harness.call(server, "export_query", siteUrl=SITE)

    assert "jane" not in q.content[0].text
    assert q.structured_content["redactedRows"] == 1
    assert c.structured_content["redactedRows"] == 2
    assert [r["keys"] for r in c.structured_content["rows"]] == [["blue widgets"]]
    with open(e.structured_content["path"], newline="") as handle:
        exported = [r["query"] for r in csv.DictReader(handle)]
    assert exported == ["blue widgets"]
    assert e.structured_content["redactedRows"] == 1
