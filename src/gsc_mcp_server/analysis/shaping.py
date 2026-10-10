"""Turn API rows into the two-part output contract.

Every performance response carries both a compact text table the model reads
and a structured block with typed rows. Raw JSON rows alone waste context and
read badly; a table alone cannot be processed.
"""

from __future__ import annotations

from typing import Any

from ..constants import ANONYMISED_QUERY_NOTE, TYPES_WITHOUT_POSITION


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
) -> tuple[str, dict[str, Any]]:
    """Return (text, structured_content) for a search analytics result."""
    compact = [compact_row(r) for r in rows]
    dimensions = request.get("dimensions") or ["query"]
    requested_limit = int(request.get("rowLimit", 0))
    start_row = int(request.get("startRow", 0))
    has_more = bool(requested_limit) and len(compact) >= requested_limit

    header = (
        f"{site_url} | {'+'.join(dimensions)} | "
        f"{request['startDate']} to {request['endDate']} | "
        f"{len(compact)} row{'' if len(compact) == 1 else 's'}"
        + (" (more available, paginate with startRow)" if has_more else "")
    )

    notes = [ANONYMISED_QUERY_NOTE]
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
    if has_more:
        structured["nextStartRow"] = start_row + len(compact)
    return text, structured
