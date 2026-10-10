"""inspect_url: URL Inspection for 1 to 10 URLs.

Calls go to searchconsole.googleapis.com v1, through gsc/client.py like
everything else. Each URL is inspected separately; one URL failing does not
discard the others.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.types import CallToolResult
from pydantic import Field

from ..constants import URL_INSPECTION_DAILY_CAP, URL_INSPECTION_MAX_URLS_PER_CALL
from ..errors import GscError
from ..gsc.quota import InspectionQuota
from ._common import READ_ONLY, SiteUrl, not_allowed, result, run_tool


def summarise(url: str, raw: dict[str, Any] | None) -> dict[str, Any]:
    """Keep the fields that answer 'is it indexed, and if not, why'."""
    raw = raw or {}
    index = raw.get("indexStatusResult") or {}
    out: dict[str, Any] = {
        "url": url,
        "ok": True,
        "verdict": index.get("verdict"),
        "coverageState": index.get("coverageState"),
        "indexingState": index.get("indexingState"),
        "robotsTxtState": index.get("robotsTxtState"),
        "pageFetchState": index.get("pageFetchState"),
        "lastCrawlTime": index.get("lastCrawlTime"),
        "crawledAs": index.get("crawledAs"),
        "googleCanonical": index.get("googleCanonical"),
        "userCanonical": index.get("userCanonical"),
        "sitemaps": index.get("sitemap") or [],
        "referringUrlCount": len(index.get("referringUrls") or []),
    }
    google, user = out["googleCanonical"], out["userCanonical"]
    if google and user:
        out["canonicalMatches"] = google == user

    mobile = raw.get("mobileUsabilityResult")
    if mobile:
        out["mobileUsability"] = mobile.get("verdict")
    rich = raw.get("richResultsResult")
    if rich:
        out["richResults"] = {
            "verdict": rich.get("verdict"),
            "types": [
                d.get("richResultType")
                for d in rich.get("detectedItems") or []
                if d.get("richResultType")
            ],
        }
    if raw.get("inspectionResultLink"):
        out["inspectionResultLink"] = raw["inspectionResultLink"]
    # Drop unset fields so the model does not read None as a finding.
    return {k: v for k, v in out.items() if v is not None}


def format_inspections(items: list[dict[str, Any]]) -> str:
    lines = []
    for item in items:
        if not item["ok"]:
            lines.append(f"{item['url']}\n  error: {item['message']}")
            continue
        parts = [
            f"verdict {item.get('verdict', '?')}",
            item.get("coverageState", "coverage unknown"),
            f"last crawl {item.get('lastCrawlTime', 'never')}",
        ]
        if item.get("canonicalMatches") is False:
            parts.append(f"Google chose canonical {item['googleCanonical']}")
        if item.get("robotsTxtState") == "DISALLOWED":
            parts.append("blocked by robots.txt")
        lines.append(f"{item['url']}\n  " + " | ".join(parts))
    return "\n".join(lines)


def register(server, context) -> None:
    quota = InspectionQuota(context.config.state_dir)

    @server.tool(
        name="inspect_url",
        title="Inspect URLs",
        description=(
            "URL Inspection for 1 to 10 URLs in one property: index verdict, "
            "coverage state, last crawl, robots.txt and fetch state, and "
            "Google's chosen canonical versus the declared one. Shows the "
            "indexed version, not a live test. Google caps this at 2,000 "
            "inspections per property per day. Read-only."
        ),
        annotations=READ_ONLY,
    )
    def inspect_url(
        siteUrl: SiteUrl,
        urls: Annotated[
            list[str],
            Field(
                min_length=1,
                max_length=URL_INSPECTION_MAX_URLS_PER_CALL,
                description="Full URLs inside siteUrl, 1 to 10.",
            ),
        ],
        languageCode: Annotated[
            str | None,
            Field(description="BCP-47 code for translated issue text, e.g. 'en-US'."),
        ] = None,
    ) -> CallToolResult:
        if not context.config.allows(siteUrl):
            return not_allowed(siteUrl)

        def body():
            items: list[dict[str, Any]] = []
            used: int | None = None
            for url in urls:
                reserved = quota.try_reserve(siteUrl)
                if reserved is None:
                    items.append(
                        {
                            "url": url,
                            "ok": False,
                            "reason": "quota_guard",
                            "message": (
                                f"Refused locally: {quota.soft_cap} URL "
                                "inspections already used today for this "
                                f"property. Google allows "
                                f"{URL_INSPECTION_DAILY_CAP} per day, reset at "
                                "midnight Pacific time. Try again tomorrow."
                            ),
                        }
                    )
                    continue
                used = reserved
                try:
                    raw = context.client.inspect_url(siteUrl, url, languageCode)
                    items.append(summarise(url, raw))
                except GscError as exc:
                    items.append(
                        {
                            "url": url,
                            "ok": False,
                            "reason": exc.reason,
                            "message": str(exc),
                        }
                    )
            inspected = sum(1 for i in items if i["ok"])
            structured = {
                "ok": inspected > 0,
                "siteUrl": siteUrl,
                "inspected": inspected,
                "quotaUsedToday": quota.used(siteUrl) if used is None else used,
                "quotaSoftCap": quota.soft_cap,
                "failed": len(items) - inspected,
                "results": items,
            }
            if not inspected:
                structured["reason"] = items[0]["reason"]
                structured["message"] = items[0]["message"]
            text = f"{siteUrl} | {inspected} of {len(items)} inspected\n"
            return result(text + format_inspections(items), structured), {
                "rows": inspected
            }

        return run_tool("inspect_url", siteUrl, body)
