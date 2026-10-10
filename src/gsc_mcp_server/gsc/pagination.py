"""Page through searchAnalytics.query with startRow.

Only export_query uses this. Inline tools stay at one page of at most
MAX_ROW_LIMIT rows so their row counts and hasMore stay honest.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ..constants import API_MAX_ROW_LIMIT
from .client import GscClient


def iter_pages(
    client: GscClient,
    site_url: str,
    body: dict[str, Any],
    *,
    max_rows: int,
    page_size: int = API_MAX_ROW_LIMIT,
) -> Iterator[list[dict[str, Any]]]:
    """Yield pages of rows until the data runs out or max_rows is reached.

    `body` is a request from build_search_analytics_request; its rowLimit and
    startRow are overridden here. A short page means the end of the data.
    """
    if max_rows < 1:
        return
    page_size = max(1, min(page_size, API_MAX_ROW_LIMIT))
    start = int(body.get("startRow", 0))
    fetched = 0
    while fetched < max_rows:
        limit = min(page_size, max_rows - fetched)
        page_body = {**body, "rowLimit": limit, "startRow": start + fetched}
        rows = client.query_search_analytics(site_url, page_body)
        if rows:
            yield rows
        fetched += len(rows)
        if len(rows) < limit:
            return
