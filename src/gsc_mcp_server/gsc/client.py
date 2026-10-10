"""Thin REST client. No Google API SDK on purpose.

Raw httpx against the documented endpoints is easier to read, easier for
contributors to follow, and avoids a layer of SDK surprises. Note the two
different hosts: Webmasters v3 for sites and search analytics, and
searchconsole.googleapis.com v1 for URL Inspection.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any
from urllib.parse import quote

import httpx

from ..auth.provider import AuthProvider
from ..constants import URL_INSPECTION_URL, WEBMASTERS_BASE
from ..errors import ApiError, GscError, NetworkError, message_for_status

logger = logging.getLogger(__name__)

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 4


class GscClient:
    def __init__(
        self,
        auth: AuthProvider,
        *,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._auth = auth
        self._client = client or httpx.Client(timeout=timeout)

    # --- plumbing ----------------------------------------------------------
    def _request(
        self, method: str, url: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        creds = self._auth.credentials()
        headers = {"Authorization": f"Bearer {creds.token}"}
        if body is not None:
            headers["Content-Type"] = "application/json"

        last: GscError | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self._client.request(method, url, headers=headers, json=body)
            except httpx.TransportError as exc:
                # Timeouts, DNS failures, dropped connections: transient, so
                # retried like a 503. Never surfaced as a bare exception.
                last = NetworkError(
                    f"Could not reach Google ({type(exc).__name__}) after "
                    f"{attempt} attempt{'' if attempt == 1 else 's'}. Check the "
                    "network connection and try again."
                )
                if attempt == MAX_ATTEMPTS:
                    raise last from exc
                self._backoff(method, url, type(exc).__name__, attempt)
                continue

            if response.is_success:
                if not response.content:
                    return {}
                try:
                    return response.json()
                except ValueError as exc:
                    raise ApiError(
                        response.status_code,
                        "Search Console returned a response that is not JSON. "
                        "Try again; if it persists, Google may be having an "
                        "outage.",
                    ) from exc

            text = response.text[:1000]
            error = ApiError(
                response.status_code,
                message_for_status(
                    response.status_code,
                    text,
                    self._auth.mode(),
                    self._auth.identity(),
                ),
                text,
            )
            if response.status_code not in RETRY_STATUSES or attempt == MAX_ATTEMPTS:
                raise error

            last = error
            self._backoff(method, url, str(response.status_code), attempt)

        raise last or ApiError(0, "Request failed with no response.")

    def _backoff(self, method: str, url: str, cause: str, attempt: int) -> None:
        delay = min(2 ** (attempt - 1), 8) + random.uniform(0, 0.3)
        # Never log the body: it can echo query strings.
        logger.warning(
            "GSC %s %s -> %s, retry %s/%s in %.1fs",
            method,
            _redact_url(url),
            cause,
            attempt,
            MAX_ATTEMPTS,
            delay,
        )
        time.sleep(delay)

    # --- API surface -------------------------------------------------------
    def list_sites(self) -> list[dict[str, Any]]:
        data = self._request("GET", f"{WEBMASTERS_BASE}/sites")
        return list(data.get("siteEntry") or [])

    def query_search_analytics(
        self, site_url: str, body: dict[str, Any]
    ) -> list[dict[str, Any]]:
        # siteUrl is matched byte for byte by Google. Never normalise it,
        # only percent-encode it for the path.
        site = quote(site_url, safe="")
        url = f"{WEBMASTERS_BASE}/sites/{site}/searchAnalytics/query"
        data = self._request("POST", url, body)
        return list(data.get("rows") or [])

    def list_sitemaps(self, site_url: str) -> list[dict[str, Any]]:
        url = f"{WEBMASTERS_BASE}/sites/{quote(site_url, safe='')}/sitemaps"
        data = self._request("GET", url)
        return list(data.get("sitemap") or [])

    def inspect_url(
        self, site_url: str, inspection_url: str, language_code: str | None = None
    ) -> dict[str, Any] | None:
        body: dict[str, Any] = {
            "siteUrl": site_url,
            "inspectionUrl": inspection_url,
        }
        if language_code:
            body["languageCode"] = language_code
        data = self._request("POST", URL_INSPECTION_URL, body)
        result = data.get("inspectionResult")
        return result if isinstance(result, dict) else None

    def close(self) -> None:
        self._client.close()


def _redact_url(url: str) -> str:
    """Keep the endpoint, drop anything that could identify a property."""
    for marker in ("/sites/",):
        if marker in url:
            head, _, tail = url.partition(marker)
            suffix = tail.split("/", 1)[1] if "/" in tail else ""
            return f"{head}{marker}<property>/{suffix}"
    return url
