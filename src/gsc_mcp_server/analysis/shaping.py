"""Turn API rows into the two-part output contract.

Every performance response carries both a compact text table the model reads
and a structured block with typed rows. Raw JSON rows alone waste context and
read badly; a table alone cannot be processed.
"""

from __future__ import annotations

import re
from typing import Any

from ..constants import ANONYMISED_QUERY_NOTE, TYPES_WITHOUT_POSITION

# GSC_REDACT_PII: a blunt filter, not a guarantee. People search for their
# own email address, phone number or account and card numbers; rows whose
# query looks like one are dropped before anything leaves the server.
_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
# A run of digits with phone-style separators. Counted afterwards, so that
# year ranges such as "2025-2026" (8 digits) survive and phone numbers,
# account and card numbers (9+ digits) do not.
_DIGIT_RUN = re.compile(r"\+?\d[\d\s().-]*\d")
_MIN_DIGITS = 9


def looks_like_pii(text: str) -> bool:
    if _EMAIL.search(text):
        return True
    return any(
        sum(c.isdigit() for c in m.group()) >= _MIN_DIGITS
        for m in _DIGIT_RUN.finditer(text)
    )


def redact_rows(
    rows: list[dict[str, Any]], dimensions: list[str]
) -> tuple[list[dict[str, Any]], int]:
    """Drop rows whose query key looks like personal data.

    Returns (kept, dropped). Only the query dimension is checked: page URLs
    routinely carry long numeric IDs and dates are digits by nature.
    """
    if "query" not in dimensions:
        return rows, 0
    index = dimensions.index("query")
    kept = []
    for row in rows:
        keys = row.get("keys") or []
        if index < len(keys) and looks_like_pii(str(keys[index])):
            continue
        kept.append(row)
    return kept, len(rows) - len(kept)


def redaction_note(dropped: int) -> str:
    return (
        f"GSC_REDACT_PII dropped {dropped} row{'' if dropped == 1 else 's'} "
        "whose query looked like personal data, so totals here are lower "
        "than in Search Console."
    )


def compact_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "keys": row.get("keys") or [],
        "clicks": int(row.get("clicks", 0)),
        "impressions": int(row.get("impressions", 0)),
        "ctr": round(float(row.get("ctr", 0.0)), 4),
    }
    # Google omits position for discover and googleNews. Absent, not zero.
    if "position" in row and row["position"] is not None:
        out["position"] = round(float(row["position"]), 1)
    return out


def format_table(rows: list[dict[str, Any]]) -> str:
    header = ("key", "clicks", "impr", "CTR", "pos")
    body: list[tuple[str, ...]] = []
    for row in rows:
        keys = row.get("keys") or []
        position = row.get("position")
        body.append(
            (
                " / ".join(str(k) for k in keys) if keys else "(total)",
                str(row.get("clicks", 0)),
                str(row.get("impressions", 0)),
                f"{float(row.get('ctr', 0.0)) * 100:.1f}%",
                f"{float(position):.1f}" if position is not None else "-",
            )
        )

    widths = [
        max(len(header[i]), *(len(r[i]) for r in body)) if body else len(header[i])
        for i in range(len(header))
    ]
    lines = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(header))]
    lines.append("  ".join("-" * widths[i] for i in range(len(header))))
    for r in body:
        lines.append("  ".join(r[i].ljust(widths[i]) for i in range(len(header))))
    return "\n".join(lines)


def performance_response(
    *,
    site_url: str,
    request: dict[str, Any],
    rows: list[dict[str, Any]],
    redact_pii: bool = False,
    top_n: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return (text, structured_content) for a search analytics result.

    With `top_n`, rows are re-ranked by clicks then impressions and cut to
    top_n. Google breaks click ties alphabetically, which on a low-traffic
    property buries the rows with the most impressions. A re-ranked result
    cannot be paginated with startRow, so it carries no nextStartRow.
    """
    dimensions = request.get("dimensions") or []
    requested_limit = int(request.get("rowLimit", 0))
    start_row = int(request.get("startRow", 0))
    # Pagination follows what Google returned, before any redaction.
    fetched = len(rows)
    has_more = bool(requested_limit) and fetched >= requested_limit
    dropped = 0
    if redact_pii:
        rows, dropped = redact_rows(rows, dimensions)
    if top_n is not None:
        rows = sorted(
            rows,
            key=lambda r: (-int(r.get("clicks", 0)), -int(r.get("impressions", 0))),
        )
        has_more = has_more or len(rows) > top_n
        rows = rows[:top_n]
    compact = [compact_row(r) for r in rows]

    if not has_more:
        more = ""
    elif top_n is not None:
        more = " (more available: use query_performance or export_query)"
    else:
        more = " (more available, paginate with startRow)"
    header = (
        f"{site_url} | {'+'.join(dimensions) or 'totals'} | "
        f"{request['startDate']} to {request['endDate']} | "
        f"{len(compact)} row{'' if len(compact) == 1 else 's'}{more}"
    )

    notes = [ANONYMISED_QUERY_NOTE]
    if dropped:
        notes.append(redaction_note(dropped))
    if request.get("type") in TYPES_WITHOUT_POSITION:
        notes.append(
            f"Google does not report position for search type "
            f"{request['type']!r}; treat it as unavailable, not an error."
        )

    text = (
        f"{header}\n{format_table(compact)}\n\nNote: {' '.join(notes)}"
        if compact
        else f"{header}\nNo rows for this range.\n\nNote: {' '.join(notes)}"
    )

    structured: dict[str, Any] = {
        "ok": True,
        "siteUrl": site_url,
        "startDate": request["startDate"],
        "endDate": request["endDate"],
        "dimensions": dimensions,
        "searchType": request.get("type", "web"),
        "dataState": request.get("dataState", "all"),
        "rowCount": len(compact),
        "rows": compact,
        "hasMore": has_more,
        "notes": notes,
    }
    if redact_pii:
        structured["redactedRows"] = dropped
    if has_more and top_n is None:
        structured["nextStartRow"] = start_row + fetched
    return text, structured
