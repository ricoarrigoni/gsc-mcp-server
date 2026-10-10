"""list_sitemaps: submitted sitemaps with their error and warning counts."""

from __future__ import annotations

from typing import Any

from mcp.types import CallToolResult

from ._common import READ_ONLY, SiteUrl, not_allowed, result, run_tool


def summarise(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "path": raw.get("path"),
        "type": raw.get("type"),
        "isPending": bool(raw.get("isPending", False)),
        "isSitemapsIndex": bool(raw.get("isSitemapsIndex", False)),
        "lastSubmitted": raw.get("lastSubmitted"),
        "lastDownloaded": raw.get("lastDownloaded"),
        # The API returns these as strings; zero when absent.
        "errors": int(raw.get("errors") or 0),
        "warnings": int(raw.get("warnings") or 0),
        "contents": [
            {"type": c.get("type"), "submitted": int(c.get("submitted") or 0)}
            for c in raw.get("contents") or []
        ],
    }
    return {k: v for k, v in out.items() if v is not None}


def format_sitemaps(items: list[dict[str, Any]]) -> str:
    lines = []
    for s in items:
        submitted = sum(c["submitted"] for c in s["contents"])
        flags = []
        if s["isPending"]:
            flags.append("pending")
        if s["isSitemapsIndex"]:
            flags.append("index")
        lines.append(
            f"{s.get('path')}  errors {s['errors']}  warnings {s['warnings']}  "
            f"submitted {submitted}  downloaded {s.get('lastDownloaded', 'never')}"
            + (f"  [{', '.join(flags)}]" if flags else "")
        )
    return "\n".join(lines)


def register(server, context) -> None:
    @server.tool(
        name="list_sitemaps",
        title="List sitemaps",
        description=(
            "Sitemaps submitted for a property, with error and warning counts, "
            "submitted URL counts and the last download time. Read-only."
        ),
        annotations=READ_ONLY,
    )
    def list_sitemaps(siteUrl: SiteUrl) -> CallToolResult:
        if not context.config.allows(siteUrl):
            return not_allowed(siteUrl)

        def body():
            items = [summarise(s) for s in context.client.list_sitemaps(siteUrl)]
            items.sort(key=lambda s: (-s["errors"], -s["warnings"], s.get("path", "")))
            structured = {
                "ok": True,
                "siteUrl": siteUrl,
                "count": len(items),
                "withErrors": sum(1 for s in items if s["errors"]),
                "sitemaps": items,
            }
            header = f"{siteUrl} | {len(items)} sitemap{'' if len(items) == 1 else 's'}"
            text = (
                f"{header}\n{format_sitemaps(items)}"
                if items
                else f"{header}\nNo sitemaps submitted."
            )
            return result(text, structured), {"rows": len(items)}

        return run_tool("list_sitemaps", siteUrl, body)
