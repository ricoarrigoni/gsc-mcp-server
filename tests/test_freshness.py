import json
from datetime import date

import httpx

from gsc_mcp_server.gsc.client import GscClient
from gsc_mcp_server.gsc.freshness import Freshness
from tests.conftest import FakeAuth

SITE = "sc-domain:example.com"
TODAY = date(2026, 10, 10)


def date_rows(*days):
    return {
        "rows": [{"keys": [d], "clicks": 1, "impressions": 1, "ctr": 1.0} for d in days]
    }


def freshness_with(responses, clock=lambda: 0.0):
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=responses.pop(0))

    client = GscClient(
        FakeAuth(), client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    return Freshness(client, today=lambda: TODAY, clock=clock), bodies


def test_check_reports_final_and_provisional_dates():
    f, bodies = freshness_with(
        [
            date_rows("2026-10-06", "2026-10-07"),
            date_rows("2026-10-07", "2026-10-09"),
        ]
    )
    info = f.check(SITE)
    assert info["latestFinalDate"] == "2026-10-07"
    assert info["latestDate"] == "2026-10-09"
    assert info["finalLagDays"] == 3
    assert [b["dataState"] for b in bodies] == ["final", "all"]
    assert bodies[0]["startDate"] == "2026-09-30"
    assert bodies[0]["dimensions"] == ["date"]


def test_empty_window_is_none_not_an_error():
    f, _ = freshness_with([{}, {}])
    info = f.check(SITE)
    assert info["latestFinalDate"] is None
    assert info["finalLagDays"] is None


def test_latest_final_is_cached_until_expiry():
    now = {"t": 0.0}
    f, bodies = freshness_with(
        [date_rows("2026-10-07"), date_rows("2026-10-08")], clock=lambda: now["t"]
    )
    assert f.latest_final(SITE) == date(2026, 10, 7)
    assert f.latest_final(SITE) == date(2026, 10, 7)
    assert len(bodies) == 1
    now["t"] = 4000.0
    assert f.latest_final(SITE) == date(2026, 10, 8)
