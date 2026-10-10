"""Diff two Search Analytics result sets server-side.

The model gets deltas, not two raw row sets to line up itself. Rows are
joined on their keys; a key present in only one window counts as zero on the
other side, except position, which stays absent when either side lacks it.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .periods import previous_period, subtract_months
from .shaping import grouping_notes, position_note, redact_rows, redaction_note


def comparison_window(
    start_date: str, end_date: str, compare_to: str
) -> tuple[str, str]:
    if compare_to == "previous_year":
        start = subtract_months(date.fromisoformat(start_date), 12)
        end = subtract_months(date.fromisoformat(end_date), 12)
        return start.isoformat(), end.isoformat()
    if compare_to == "previous_period":
        return previous_period(start_date, end_date)
    raise ValueError(
        f"Unknown compareTo {compare_to!r}. Use previous_period or previous_year."
    )


def _metrics(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {"clicks": 0, "impressions": 0, "ctr": 0.0}
    out: dict[str, Any] = {
        "clicks": int(row.get("clicks", 0)),
        "impressions": int(row.get("impressions", 0)),
        "ctr": round(float(row.get("ctr", 0.0)), 4),
    }
    if row.get("position") is not None:
        out["position"] = round(float(row["position"]), 1)
    return out


def diff_rows(
    current: list[dict[str, Any]], previous: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Join on keys, compute deltas, sort by absolute click change."""
    cur = {tuple(r.get("keys") or []): r for r in current}
    prev = {tuple(r.get("keys") or []): r for r in previous}

    out: list[dict[str, Any]] = []
    for keys in list(cur) + [k for k in prev if k not in cur]:
        a = _metrics(cur.get(keys))
        b = _metrics(prev.get(keys))
        delta: dict[str, Any] = {
            "clicks": a["clicks"] - b["clicks"],
            "impressions": a["impressions"] - b["impressions"],
            "ctr": round(a["ctr"] - b["ctr"], 4),
        }
        # Lower position is better. Only diff it when both sides have one.
        if "position" in a and "position" in b:
            delta["position"] = round(a["position"] - b["position"], 1)
        out.append(
            {
                "keys": list(keys),
                "current": a,
                "previous": b,
                "delta": delta,
                "status": (
                    "new"
                    if keys not in prev
                    else "lost"
                    if keys not in cur
                    else "changed"
                ),
            }
        )
    out.sort(key=lambda r: (-abs(r["delta"]["clicks"]), -r["current"]["clicks"]))
    return out


def _signed(value: float, fmt: str = "{:+d}") -> str:
    return fmt.format(value)


def format_comparison_table(rows: list[dict[str, Any]]) -> str:
    header = ("key", "clicks", "Δclicks", "impr", "Δimpr", "CTR", "pos", "Δpos")
    body: list[tuple[str, ...]] = []
    for r in rows:
        cur, delta = r["current"], r["delta"]
        label = " / ".join(str(k) for k in r["keys"]) or "(total)"
        if r["status"] != "changed":
            label = f"{label} [{r['status']}]"
        body.append(
            (
                label,
                str(cur["clicks"]),
                _signed(delta["clicks"]),
                str(cur["impressions"]),
                _signed(delta["impressions"]),
                f"{cur['ctr'] * 100:.1f}%",
                f"{cur['position']:.1f}" if "position" in cur else "-",
                _signed(delta["position"], "{:+.1f}") if "position" in delta else "-",
            )
        )
    widths = [
        max(len(header[i]), *(len(b[i]) for b in body)) if body else len(header[i])
        for i in range(len(header))
    ]
    lines = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(header))]
    lines.append("  ".join("-" * w for w in widths))
    lines.extend(
        "  ".join(b[i].ljust(widths[i]) for i in range(len(header))) for b in body
    )
    return "\n".join(lines)


def comparison_response(
    *,
    site_url: str,
    current_request: dict[str, Any],
    previous_request: dict[str, Any],
    current_rows: list[dict[str, Any]],
    previous_rows: list[dict[str, Any]],
    limit: int,
    redact_pii: bool = False,
) -> tuple[str, dict[str, Any]]:
    dimensions = current_request.get("dimensions") or []
    fetch_limit = int(current_request.get("rowLimit", 0))
    truncated = bool(fetch_limit) and (
        len(current_rows) >= fetch_limit or len(previous_rows) >= fetch_limit
    )
    dropped = 0
    if redact_pii:
        current_rows, cur_dropped = redact_rows(current_rows, dimensions)
        previous_rows, prev_dropped = redact_rows(previous_rows, dimensions)
        dropped = cur_dropped + prev_dropped
    diffed = diff_rows(current_rows, previous_rows)
    shown = diffed[:limit]

    def totals(rows: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "clicks": sum(int(r.get("clicks", 0)) for r in rows),
            "impressions": sum(int(r.get("impressions", 0)) for r in rows),
        }

    cur_tot, prev_tot = totals(current_rows), totals(previous_rows)

    notes = grouping_notes(dimensions)
    if dropped:
        notes.append(redaction_note(dropped))
    if truncated:
        notes.append(
            f"One window hit the {fetch_limit}-row fetch cap, so keys outside "
            "the top rows of either window may show as new or lost when they "
            "are not. Narrow with filters for an exact diff."
        )
    notes += position_note(current_request.get("type"))

    header = (
        f"{site_url} | {'+'.join(dimensions) or 'totals'} | "
        f"{current_request['startDate']} to {current_request['endDate']} vs "
        f"{previous_request['startDate']} to {previous_request['endDate']} | "
        f"clicks {cur_tot['clicks']} ({cur_tot['clicks'] - prev_tot['clicks']:+d}), "
        f"impr {cur_tot['impressions']} "
        f"({cur_tot['impressions'] - prev_tot['impressions']:+d})"
    )
    table = format_comparison_table(shown) if shown else "No rows in either window."
    text = (
        f"{header}\nTop {len(shown)} of {len(diffed)} by absolute click change\n"
        f"{table}\n\nNote: {' '.join(notes)}"
    )

    structured: dict[str, Any] = {
        "ok": True,
        "siteUrl": site_url,
        "dimensions": dimensions,
        "searchType": current_request.get("type", "web"),
        "current": {
            "startDate": current_request["startDate"],
            "endDate": current_request["endDate"],
            **cur_tot,
        },
        "previous": {
            "startDate": previous_request["startDate"],
            "endDate": previous_request["endDate"],
            **prev_tot,
        },
        "rowCount": len(shown),
        "totalKeys": len(diffed),
        "rows": shown,
        "hasMore": len(diffed) > len(shown),
        "truncated": truncated,
        "notes": notes,
    }
    if redact_pii:
        structured["redactedRows"] = dropped
    return text, structured
