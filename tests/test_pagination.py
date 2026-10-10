import json

import httpx

from gsc_mcp_server.gsc.client import GscClient
from gsc_mcp_server.gsc.pagination import iter_pages
from tests.conftest import FakeAuth


def paged_client(total: int):
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        start, limit = body.get("startRow", 0), body["rowLimit"]
        rows = [
            {"keys": [str(i)], "clicks": 1, "impressions": 1, "ctr": 1.0}
            for i in range(start, min(start + limit, total))
        ]
        return httpx.Response(200, json={"rows": rows})

    client = GscClient(
        FakeAuth(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    return client, bodies


BODY = {"startDate": "2026-09-01", "endDate": "2026-09-28", "rowLimit": 1000}


def test_pages_until_a_short_page():
    client, bodies = paged_client(25)
    pages = list(
        iter_pages(client, "sc-domain:example.com", BODY, max_rows=100, page_size=10)
    )
    assert [len(p) for p in pages] == [10, 10, 5]
    assert [b["startRow"] for b in bodies] == [0, 10, 20]


def test_exact_multiple_needs_one_empty_page_to_stop():
    client, bodies = paged_client(20)
    pages = list(
        iter_pages(client, "sc-domain:example.com", BODY, max_rows=100, page_size=10)
    )
    assert sum(len(p) for p in pages) == 20
    assert len(bodies) == 3


def test_max_rows_stops_early_and_shrinks_the_last_page():
    client, bodies = paged_client(1000)
    pages = list(
        iter_pages(client, "sc-domain:example.com", BODY, max_rows=25, page_size=10)
    )
    assert sum(len(p) for p in pages) == 25
    assert bodies[-1]["rowLimit"] == 5


def test_page_size_is_capped_at_the_api_maximum():
    client, bodies = paged_client(0)
    list(
        iter_pages(
            client, "sc-domain:example.com", BODY, max_rows=100_000, page_size=99_999
        )
    )
    assert bodies[0]["rowLimit"] == 25_000
