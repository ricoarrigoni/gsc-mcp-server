"""Logging that cannot leak search data.

The server logs tool name, property, date range, row count and duration.
It never logs rows, query strings or token material. The filter below is a
backstop for accidental interpolation.
"""

from __future__ import annotations

import logging
import re
import sys

_PATTERNS = [
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(\"?refresh_token\"?\s*[:=]\s*\"?)[^\s\",}]+"),
    re.compile(r"(?i)(\"?access_token\"?\s*[:=]\s*\"?)[^\s\",}]+"),
    re.compile(r"(?i)(\"?client_secret\"?\s*[:=]\s*\"?)[^\s\",}]+"),
    re.compile(r"(?i)(ya29\.)[A-Za-z0-9._\-]+"),
    re.compile(r"(1//)[A-Za-z0-9._\-]{10,}"),
]


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover
            return True
        cleaned = message
        for pattern in _PATTERNS:
            cleaned = pattern.sub(r"\1<redacted>", cleaned)
        if cleaned != message:
            record.msg = cleaned
            record.args = ()
        return True


def configure(level: int = logging.INFO) -> None:
    # stderr only: stdout is the stdio transport's JSON-RPC channel.
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    )
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # httpx logs every request URL at INFO. A searchAnalytics URL contains the
    # property, so that is property data in the log. Our own log lines redact
    # it; httpx's do not. Silence them below WARNING.
    for noisy in ("httpx", "httpcore", "urllib3", "google_auth_httplib2"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
