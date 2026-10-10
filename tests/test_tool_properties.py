import httpx

from tests.conftest import load_fixture


async def test_list_properties_returns_structured_content(harness):
    harness.queue(load_fixture("sites_list.json"))
    server = harness.server()

    out = await harness.call(server, "list_properties")

    assert out.structured_content["ok"] is True
    assert out.structured_content["count"] == 3
    assert out.structured_content["properties"][0]["siteUrl"] == (
        "sc-domain:example.com"
    )


async def test_list_properties_honours_the_allowlist(harness):
    harness.queue(load_fixture("sites_list.json"))
    server = harness.server(property_allowlist=("https://example.com/",))

    out = await harness.call(server, "list_properties")

    assert [p["siteUrl"] for p in out.structured_content["properties"]] == [
        "https://example.com/"
    ]


async def test_list_properties_maps_api_errors_to_ok_false(harness):
    harness.queue(httpx.Response(403, text="forbidden"))
    server = harness.server()

    out = await harness.call(server, "list_properties")

    assert out.structured_content["ok"] is False
    assert out.structured_content["reason"] == "api_error"


async def test_every_tool_is_annotated_read_only(harness):
    server = harness.server()
    tools = await server.list_tools()

    assert len(tools) <= 9
    for tool in tools:
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False
        assert tool.annotations.open_world_hint is False
