"""list_properties: the one tool implemented in the scaffold.

It exists so the whole chain can be proved end to end (config, auth, scope
assertion, HTTP, error mapping, MCP registration) before any other tool is
written. Use it as the pattern for the rest.
"""

from __future__ import annotations

import time
from typing import Any

from ..errors import GscError, empty_property_list_message
from ._common import READ_ONLY, failure, log_call


def register(server, context) -> None:
    @server.tool(
        name="list_properties",
        title="List Search Console properties",
        description=(
            "List the Google Search Console properties this server can read, "
            "with the permission level on each. siteUrl is returned verbatim "
            "and must be passed back verbatim to other tools: Search Console "
            "matches it byte for byte, so 'sc-domain:example.com' and "
            "'https://example.com/' are different properties. Read-only."
        ),
        annotations=READ_ONLY,
    )
    def list_properties() -> dict[str, Any]:
        started = time.monotonic()
        try:
            sites = context.client.list_sites()
        except GscError as exc:
            log_call("list_properties", started, outcome=exc.reason)
            return failure(exc.reason, str(exc))
        allowed = [s for s in sites if context.config.allows(s.get("siteUrl", ""))]

        log_call("list_properties", started, rows=len(allowed))
        if not allowed:
            return {
                "ok": False,
                "reason": "no_properties",
                "message": empty_property_list_message(
                    context.auth.mode(), context.auth.identity()
                ),
            }

        return {
            "ok": True,
            "authMode": context.auth.mode(),
            "count": len(allowed),
            "properties": [
                {
                    "siteUrl": s.get("siteUrl"),
                    "permissionLevel": s.get("permissionLevel"),
                }
                for s in allowed
            ],
        }
