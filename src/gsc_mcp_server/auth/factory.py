"""Pick the provider from config, and assert the read-only guarantee."""

from __future__ import annotations

from ..config import Config
from ..constants import SCOPE_READONLY, SCOPE_WRITE
from ..errors import ScopeTooWideError
from .oauth_user import OAuthUserProvider
from .provider import AuthProvider
from .service_account import ServiceAccountProvider


def build_auth_provider(cfg: Config) -> AuthProvider:
    if cfg.auth_mode == "service_account":
        return ServiceAccountProvider(cfg)
    return OAuthUserProvider(cfg)


def assert_read_only(provider: AuthProvider) -> None:
    """Refuse to run with anything wider than the read-only scope.

    This is the strongest security control in the project and it costs
    nothing. A credential that can write to Search Console must never be
    handed to a language model by this server.
    """
    scopes = set(provider.granted_scopes())
    if SCOPE_WRITE in scopes:
        raise ScopeTooWideError(
            "This credential grants the read-write Search Console scope "
            f"({SCOPE_WRITE}). This server is read-only by design and will "
            "not run with a write scope. Re-authorise with only "
            f"{SCOPE_READONLY}."
        )
    if SCOPE_READONLY not in scopes:
        raise ScopeTooWideError(
            f"This credential does not grant {SCOPE_READONLY}. Re-run "
            "`gsc-mcp-server auth`."
        )
