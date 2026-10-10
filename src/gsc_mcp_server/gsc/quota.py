"""Local daily counter for URL Inspection.

Google caps URL Inspection per property per day. Counting locally and
refusing at URL_INSPECTION_SOFT_CAP makes the refusal ours, with a legible
message, instead of a 429 halfway through a batch. The count persists in
state_dir so restarting the server does not reset it.

Google's per-day quotas reset at midnight Pacific time, so the day is taken
in that zone. Where no tz database is available the day falls back to UTC.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

from ..constants import URL_INSPECTION_SOFT_CAP

logger = logging.getLogger(__name__)

STATE_FILE = "url_inspection_quota.json"


def _pacific_today() -> date:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/Los_Angeles")).date()
    except Exception:  # ZoneInfoNotFoundError, or no tz database at all
        return datetime.now(UTC).date()


class InspectionQuota:
    def __init__(
        self,
        state_dir: Path,
        *,
        soft_cap: int = URL_INSPECTION_SOFT_CAP,
        today: Callable[[], date] = _pacific_today,
    ) -> None:
        self._path = state_dir / STATE_FILE
        self._soft_cap = soft_cap
        self._today = today
        self._lock = threading.Lock()

    @property
    def soft_cap(self) -> int:
        return self._soft_cap

    def _load(self) -> dict[str, int]:
        try:
            data = json.loads(self._path.read_text())
        except (FileNotFoundError, ValueError):
            return {}
        if data.get("date") != self._today().isoformat():
            return {}
        counts = data.get("counts")
        return dict(counts) if isinstance(counts, dict) else {}

    def _save(self, counts: dict[str, int]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump({"date": self._today().isoformat(), "counts": counts}, handle)
        tmp.replace(self._path)

    def used(self, site_url: str) -> int:
        with self._lock:
            return int(self._load().get(site_url, 0))

    def try_reserve(self, site_url: str) -> bool:
        """Count one inspection if under the soft cap. False means refuse."""
        with self._lock:
            counts = self._load()
            current = int(counts.get(site_url, 0))
            if current >= self._soft_cap:
                return False
            counts[site_url] = current + 1
            try:
                self._save(counts)
            except OSError as exc:
                # Failing open is right here: Google still enforces the real
                # cap. Say so once per failure, without the property.
                logger.warning("could not persist URL Inspection count: %s", exc)
            return True
