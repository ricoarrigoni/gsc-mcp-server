"""`gsc-mcp-server doctor`: the diagnostic that replaces a docs page.

Every check prints pass or fail plus the next action on failure. If someone
opens an issue, the doctor output is the first thing to ask for.
"""

from __future__ import annotations

from dataclasses import dataclass

from .auth import build_auth_provider
from .auth.service_account import ServiceAccountProvider
from .config import Config
from .constants import SCOPE_READONLY, SCOPE_WRITE
from .errors import empty_property_list_message
from .gsc import GscClient

OK = "ok"
WARN = "warn"
FAIL = "fail"


@dataclass
class Check:
    name: str
    status: str
    detail: str


def run_doctor(cfg: Config | None = None) -> list[Check]:
    cfg = cfg or Config.from_env()
    checks: list[Check] = []

    checks.append(Check("auth mode", OK, cfg.auth_mode))

    # --- credential present ------------------------------------------------
    try:
        provider = build_auth_provider(cfg)
    except Exception as exc:
        checks.append(Check("provider", FAIL, str(exc)))
        return checks

    if isinstance(provider, ServiceAccountProvider):
        warning = provider.key_permissions_warning()
        if warning:
            checks.append(Check("key file permissions", WARN, warning))

    # granted_scopes() is what actually touches the stored credential, so it
    # is the honest place to decide whether one exists at all.
    try:
        scopes = set(provider.granted_scopes())
        identity = provider.identity()
    except Exception as exc:
        checks.append(Check("credential", FAIL, str(exc)))
        return checks

    checks.append(Check("credential", OK, identity or "loaded (identity unknown)"))

    # --- scope -------------------------------------------------------------

    if SCOPE_WRITE in scopes:
        checks.append(
            Check(
                "scope",
                FAIL,
                "Credential grants the read-write scope. This server refuses "
                "to run with it. Re-authorise with read-only only.",
            )
        )
    elif SCOPE_READONLY not in scopes:
        checks.append(
            Check(
                "scope",
                FAIL,
                f"Credential does not grant {SCOPE_READONLY}. Re-run "
                "`gsc-mcp-server auth`.",
            )
        )
    else:
        checks.append(Check("scope", OK, "webmasters.readonly only"))

    # --- token refresh -----------------------------------------------------
    try:
        provider.credentials()
        checks.append(Check("token", OK, "valid"))
    except Exception as exc:
        checks.append(Check("token", FAIL, str(exc)))
        return checks

    # --- reachable properties ---------------------------------------------
    client = GscClient(provider)
    try:
        sites = client.list_sites()
    except Exception as exc:
        checks.append(Check("properties", FAIL, str(exc)))
        return checks
    finally:
        client.close()

    if not sites:
        checks.append(
            Check(
                "properties",
                FAIL,
                empty_property_list_message(provider.mode(), provider.identity()),
            )
        )
    else:
        names = ", ".join(s.get("siteUrl", "?") for s in sites[:5])
        more = f" (+{len(sites) - 5} more)" if len(sites) > 5 else ""
        checks.append(Check("properties", OK, f"{len(sites)}: {names}{more}"))

    # --- allowlist ---------------------------------------------------------
    if cfg.property_allowlist:
        blocked = [
            s.get("siteUrl") for s in sites if not cfg.allows(s.get("siteUrl", ""))
        ]
        checks.append(
            Check(
                "allowlist",
                OK,
                f"{len(cfg.property_allowlist)} allowed, "
                f"{len(blocked)} visible property/properties blocked",
            )
        )

    return checks
