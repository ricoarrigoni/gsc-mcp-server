from tests.conftest import load_fixture

SITE = "https://example.com/"


async def test_list_sitemaps_puts_errors_first_and_counts_as_ints(harness):
    harness.queue(load_fixture("sitemaps_list.json"))
    server = harness.server()

    out = await harness.call(server, "list_sitemaps", siteUrl=SITE)

    sitemaps = out.structured_content["sitemaps"]
    assert sitemaps[0]["path"].endswith("news-sitemap.xml")
    assert sitemaps[0]["errors"] == 2
    assert sitemaps[1]["contents"] == [{"type": "web", "submitted": 412}]
    assert out.structured_content["withErrors"] == 1
    assert "pending" in out.content[0].text


async def test_list_sitemaps_encodes_the_site_url(harness):
    server = harness.server()
    out = await harness.call(server, "list_sitemaps", siteUrl=SITE)
    assert "/sites/https%3A%2F%2Fexample.com%2F/sitemaps" in str(
        harness.requests[0].url
    )
    assert out.structured_content["count"] == 0


async def test_list_sitemaps_honours_the_allowlist(harness):
    server = harness.server(property_allowlist=("sc-domain:example.com",))
    out = await harness.call(server, "list_sitemaps", siteUrl=SITE)
    assert out.structured_content["reason"] == "property_not_allowed"
    assert harness.requests == []
