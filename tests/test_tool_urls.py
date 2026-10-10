import json

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from gsc_mcp_server.constants import URL_INSPECTION_SOFT_CAP
from gsc_mcp_server.gsc.quota import STATE_FILE, _pacific_today
from tests.conftest import load_fixture

SITE = "sc-domain:example.com"


async def test_inspect_url_summarises_the_index_status(harness):
    harness.queue(load_fixture("url_inspection.json"))
    server = harness.server()

    out = await harness.call(
        server, "inspect_url", siteUrl=SITE, urls=["https://example.com/widgets"]
    )

    item = out.structured_content["results"][0]
    assert item["verdict"] == "PASS"
    assert item["canonicalMatches"] is False
    assert item["referringUrlCount"] == 2
    assert item["richResults"]["types"] == ["Breadcrumbs"]
    assert "Google chose canonical" in out.content[0].text


async def test_inspect_url_sends_site_url_verbatim_in_the_body(harness):
    server = harness.server()
    await harness.call(
        server, "inspect_url", siteUrl=SITE, urls=["https://example.com/a"]
    )
    request = harness.requests[0]
    assert request.url.host == "searchconsole.googleapis.com"
    assert json.loads(request.content)["siteUrl"] == SITE


async def test_one_failing_url_does_not_discard_the_others(harness):
    harness.queue(
        httpx.Response(400, text="not in property"),
        load_fixture("url_inspection.json"),
    )
    server = harness.server()
    out = await harness.call(
        server,
        "inspect_url",
        siteUrl=SITE,
        urls=["https://example.org/x", "https://example.com/widgets"],
    )
    assert out.structured_content["ok"] is True
    assert out.structured_content["inspected"] == 1
    assert out.structured_content["results"][0]["ok"] is False


async def test_all_urls_failing_is_ok_false(harness):
    harness.queue(httpx.Response(403, text="forbidden"))
    server = harness.server()
    out = await harness.call(
        server, "inspect_url", siteUrl=SITE, urls=["https://example.com/a"]
    )
    assert out.structured_content["ok"] is False
    assert out.structured_content["reason"] == "api_error"


async def test_more_than_ten_urls_is_refused_by_schema(harness):
    server = harness.server()
    urls = [f"https://example.com/{i}" for i in range(11)]
    with pytest.raises(ToolError):
        await harness.call(server, "inspect_url", siteUrl=SITE, urls=urls)
    assert harness.requests == []


async def test_inspect_url_honours_the_allowlist(harness):
    server = harness.server(property_allowlist=("https://example.com/",))
    out = await harness.call(
        server, "inspect_url", siteUrl=SITE, urls=["https://example.com/a"]
    )
    assert out.structured_content["reason"] == "property_not_allowed"


async def test_inspect_url_refuses_locally_at_the_soft_cap(harness):
    state = harness.tmp_path / "state"
    state.mkdir()
    (state / STATE_FILE).write_text(
        json.dumps(
            {
                "date": _pacific_today().isoformat(),
                "counts": {SITE: URL_INSPECTION_SOFT_CAP - 1},
            }
        )
    )
    server = harness.server()
    out = await harness.call(
        server,
        "inspect_url",
        siteUrl=SITE,
        urls=["https://example.com/a", "https://example.com/b"],
    )
    results = out.structured_content["results"]
    assert results[0]["ok"] is True
    assert results[1]["reason"] == "quota_guard"
    assert len(harness.requests) == 1
    assert out.structured_content["quotaUsedToday"] == URL_INSPECTION_SOFT_CAP
