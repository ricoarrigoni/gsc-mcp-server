"""How recent the data actually is, per property.

Search Console usually finalises data 2 to 3 days back, but not always.
Rather than trusting DATA_LAG_DAYS, ask: query the last 10 days grouped by
date and take the latest date present. Tools that do date maths anchor on
this. Results are cached briefly, since they change at most daily.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from .client import GscClient

LOOKBACK_DAYS = 10
CACHE_SECONDS = 3600


class Freshness:
    def __init__(
        self,
        client: GscClient,
        *,
        today: Callable[[], date] = date.today,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._today = today
        self._clock = clock
        self._cache: dict[str, tuple[float, date | None]] = {}
        self._lock = threading.Lock()

    def _latest(self, site_url: str, data_state: str) -> date | None:
        today = self._today()
        body: dict[str, Any] = {
            "startDate": (today - timedelta(days=LOOKBACK_DAYS)).isoformat(),
            "endDate": today.isoformat(),
            "dimensions": ["date"],
            "rowLimit": LOOKBACK_DAYS + 1,
            "type": "web",
            "dataState": data_state,
        }
        rows = self._client.query_search_analytics(site_url, body)
        dates = [r["keys"][0] for r in rows if r.get("keys")]
        return date.fromisoformat(max(dates)) if dates else None

    def check(self, site_url: str) -> dict[str, Any]:
        """Latest final and latest provisional dates. Two API calls, uncached."""
        today = self._today()
        final = self._latest(site_url, "final")
        provisional = self._latest(site_url, "all")
        with self._lock:
            self._cache[site_url] = (self._clock() + CACHE_SECONDS, final)
        return {
            "today": today.isoformat(),
            "lookbackStart": (today - timedelta(days=LOOKBACK_DAYS)).isoformat(),
            "latestFinalDate": final.isoformat() if final else None,
            "latestDate": provisional.isoformat() if provisional else None,
            "finalLagDays": (today - final).days if final else None,
        }

    def latest_final(self, site_url: str) -> date | None:
        """Latest date with final data, cached. None when the window is empty."""
        with self._lock:
            hit = self._cache.get(site_url)
            if hit and hit[0] > self._clock():
                return hit[1]
        final = self._latest(site_url, "final")
        with self._lock:
            self._cache[site_url] = (self._clock() + CACHE_SECONDS, final)
        return final
