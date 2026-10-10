"""Shared pieces for every tool module.

Annotations, the failure shape, the allowlist check and the one log line per
call live here so the tool modules cannot drift apart on any of them.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Annotated, Any

from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, Field

from ..constants import DateRange, Dimension, FilterOperator, SearchType
from ..errors import GscError

logger = logging.getLogger("gsc_mcp_server.tools")

READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    open_world_hint=False,
)


# --- Parameter types shared by the Search Analytics tools ------------------
# Parameter names are camelCase to match the API fields and the descriptions
# the model reads; the SDK does not honour pydantic aliases on tool args.

SiteUrl = Annotated[
    str,
    Field(
        description=(
            "Property exactly as list_properties returns it, e.g. "
            "'sc-domain:example.com' or 'https://example.com/'. Passed "
            "verbatim: Search Console matches it byte for byte."
        )
    ),
]
DateRangeArg = Annotated[
    DateRange | None,
    Field(
        description=(
            "Named window ending 3 days ago (data lag). Default last_28_days. "
            "Ignored when startDate and endDate are both given."
        )
    ),
]
StartDate = Annotated[
    str | None,
    Field(description="YYYY-MM-DD. Give both startDate and endDate, or neither."),
]
EndDate = Annotated[
    str | None,
    Field(description="YYYY-MM-DD. Give both startDate and endDate, or neither."),
]
SearchTypeArg = Annotated[
    SearchType,
    Field(
        description=(
            "Search surface. Position is not reported for discover and googleNews."
        )
    ),
]


class Filter(BaseModel):
    """One dimension filter. Several are combined with AND."""

    dimension: Dimension
    operator: FilterOperator = "equals"
    expression: str = Field(min_length=1)


FiltersArg = Annotated[
    list[Filter] | None,
    Field(
        description=(
            "Filters, combined with AND. country takes lowercase ISO 3166-1 "
            "alpha-3 (e.g. 'usa'); device takes DESKTOP, MOBILE or TABLET."
        )
    ),
]


def filter_dicts(filters: list[Filter] | None) -> list[dict[str, Any]]:
    return [f.model_dump() for f in filters or []]


def failure(reason: str, message: str) -> dict[str, Any]:
    """The structured failure shape: `ok` false, a stable `reason`, a fix."""
    return {"ok": False, "reason": reason, "message": message}


def result(text: str, structured: dict[str, Any]) -> CallToolResult:
    """Text the model reads plus structured content it can process."""
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=structured,
    )


def failure_result(reason: str, message: str) -> CallToolResult:
    return result(message, failure(reason, message))


def not_allowed(site_url: str) -> CallToolResult:
    return failure_result(
        "property_not_allowed",
        f"{site_url} is not in GSC_PROPERTY_ALLOWLIST. Add it there, or use "
        "list_properties to see the properties this server may read.",
    )


def run_tool(
    tool: str,
    site_url: str | None,
    body: Callable[[], tuple[CallToolResult, dict[str, Any]]],
) -> CallToolResult:
    """Run a tool body, map known errors to `ok: false`, log one line.

    `body` returns the result plus log fields (startDate, endDate, rows).
    Only those fields are logged: never rows, query text or tokens.
    """
    started = time.monotonic()
    fields: dict[str, Any] = {}
    outcome = "unexpected_error"
    try:
        out, fields = body()
        outcome = "ok"
        return out
    except ValueError as exc:
        # RequestValidationError, plus date errors from analysis/periods.py.
        outcome = "invalid_request"
        return failure_result("invalid_request", str(exc))
    except GscError as exc:
        outcome = exc.reason
        return failure_result(exc.reason, str(exc))
    except OSError as exc:
        # export_query writing to disk: a full disk or an unwritable dir.
        outcome = "io_error"
        return failure_result(
            "io_error",
            f"Could not write the file: {exc.strerror or exc}. Check "
            "GSC_EXPORT_DIR points at a writable directory.",
        )
    except Exception as exc:
        # Anything unforeseen still comes back as ok: false with a next step,
        # never as a bare MCP error. Log the type only: messages can carry
        # request data.
        logger.error("tool=%s unexpected %s", tool, type(exc).__name__)
        return failure_result(
            "unexpected_error",
            f"Unexpected error ({type(exc).__name__}). Try again. If it "
            "repeats, run `gsc-mcp-server doctor` and report the server log.",
        )
    finally:
        log_call(
            tool,
            started,
            site_url=site_url,
            start_date=fields.get("startDate"),
            end_date=fields.get("endDate"),
            rows=fields.get("rows"),
            outcome=outcome,
        )


def log_call(
    tool: str,
    started: float,
    *,
    site_url: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    rows: int | None = None,
    outcome: str = "ok",
) -> None:
    """The one log line per tool call. Only these fields, nothing else."""
    logger.info(
        "tool=%s property=%s range=%s..%s rows=%s duration_ms=%d outcome=%s",
        tool,
        site_url or "-",
        start_date or "-",
        end_date or "-",
        "-" if rows is None else rows,
        (time.monotonic() - started) * 1000,
        outcome,
    )
