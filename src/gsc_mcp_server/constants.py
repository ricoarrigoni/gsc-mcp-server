"""Single source of truth for API option sets and limits.

These drive both the outbound API calls and the MCP tool schemas, so the two
cannot drift apart.
"""

from __future__ import annotations

from typing import Final, Literal

# --- Endpoints -------------------------------------------------------------
# Two different hosts. Google's own docs are inconsistent about the version
# string; these are the paths that work.
WEBMASTERS_BASE: Final = "https://www.googleapis.com/webmasters/v3"
URL_INSPECTION_URL: Final = (
    "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
)
USERINFO_URL: Final = "https://openidconnect.googleapis.com/v1/userinfo"

# --- Scopes ----------------------------------------------------------------
# Read-only, and never anything wider. The read-only guarantee is enforced by
# Google against this scope, not by code in this repo.
SCOPE_READONLY: Final = "https://www.googleapis.com/auth/webmasters.readonly"
SCOPE_WRITE: Final = "https://www.googleapis.com/auth/webmasters"
OAUTH_SCOPES: Final = (
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    SCOPE_READONLY,
)
SERVICE_ACCOUNT_SCOPES: Final = (SCOPE_READONLY,)

# --- Search Analytics option sets -----------------------------------------
DIMENSIONS: Final = ("query", "page", "country", "device", "date", "searchAppearance")
FILTER_OPERATORS: Final = (
    "equals",
    "notEquals",
    "contains",
    "notContains",
    "includingRegex",
    "excludingRegex",
)
SEARCH_TYPES: Final = ("web", "image", "video", "news", "googleNews", "discover")
DATA_STATES: Final = ("final", "all")
DATE_RANGES: Final = (
    "last_7_days",
    "last_28_days",
    "last_3_months",
    "last_6_months",
    "last_12_months",
    "last_16_months",
)

Dimension = Literal["query", "page", "country", "device", "date", "searchAppearance"]
SearchType = Literal["web", "image", "video", "news", "googleNews", "discover"]
DateRange = Literal[
    "last_7_days",
    "last_28_days",
    "last_3_months",
    "last_6_months",
    "last_12_months",
    "last_16_months",
]

# searchAppearance cannot be combined with any other dimension. The API
# rejects it, so validate before the call.
EXCLUSIVE_DIMENSIONS: Final = frozenset({"searchAppearance"})

# Google omits position for these search types even though the other metrics
# are present. Treat a missing position as unavailable, not as a failure.
TYPES_WITHOUT_POSITION: Final = frozenset({"discover", "googleNews"})

# --- Limits ----------------------------------------------------------------
# The API allows 25000 rows per call. We cap at 1000 so fetched == returned,
# which keeps row counts and hasMore honest and keeps the model's context
# window intact. Larger pulls go through the CSV export tool.
DEFAULT_ROW_LIMIT: Final = 1000
MAX_ROW_LIMIT: Final = 1000
API_MAX_ROW_LIMIT: Final = 25_000

# Search Console data trails real time by 2 to 3 days.
DATA_LAG_DAYS: Final = 3
# Nothing older than 16 months exists.
RETENTION_MONTHS: Final = 16

# URL Inspection is capped per site per day by Google. Refuse before hitting
# it so the error is ours and legible.
URL_INSPECTION_DAILY_CAP: Final = 2000
URL_INSPECTION_SOFT_CAP: Final = 1900
URL_INSPECTION_MAX_URLS_PER_CALL: Final = 10

# --- Caveat text reused in every performance response ---------------------
ANONYMISED_QUERY_NOTE: Final = (
    "Query rows exclude anonymised queries, so they will not sum to the "
    "property totals. Grouping by page or query also drops some rows."
)
