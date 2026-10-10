"""Errors, with messages that differ by auth mode.

The same HTTP status means different things depending on how the server
authenticated, so there is no single generic string. A caller should always
get a sentence naming the next action.
"""

from __future__ import annotations

from .config import AuthMode


class GscError(Exception):
    """Base class. `reason` is a stable machine code for structured output."""

    reason = "error"


class ConfigError(GscError):
    reason = "config_error"


class AuthNotConfiguredError(ConfigError):
    reason = "auth_not_configured"


class ScopeTooWideError(ConfigError):
    reason = "scope_too_wide"


class TokenError(GscError):
    reason = "token_error"

    @staticmethod
    def for_mode(mode: AuthMode) -> TokenError:
        if mode == "service_account":
            return TokenError(
                "The service account key was rejected. It may have been "
                "revoked or deleted. Generate a new key in Google Cloud "
                "Console and point GSC_SERVICE_ACCOUNT_KEY at it."
            )
        return TokenError(
            "The Google authorisation expired or was revoked. Run "
            "`gsc-mcp-server auth` to sign in again. If this happens every "
            "week, your OAuth app is still in Testing status: publish it to "
            "In production in Google Cloud Console."
        )


class ApiError(GscError):
    reason = "api_error"

    def __init__(self, status: int, message: str, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


class QuotaError(GscError):
    reason = "quota_error"


class PropertyNotAllowedError(GscError):
    reason = "property_not_allowed"


def message_for_status(
    status: int, body: str, mode: AuthMode, identity: str | None
) -> str:
    """Map an HTTP status to a sentence that names the fix for this mode."""
    who = identity or "the configured credential"

    if status in (401, 403):
        if mode == "service_account":
            return (
                "Search Console denied access. Add "
                f"{who} as a user on this property in Search Console, under "
                "Settings, Users and permissions."
            )
        return (
            f"Search Console denied access. The Google account {who} does not "
            "have permission on this property, or the authorisation was "
            "revoked. Run `gsc-mcp-server auth` to sign in again."
        )
    if status == 404:
        return (
            "Search Console property not found. Check the siteUrl is exactly "
            "as Search Console reports it, including the sc-domain: prefix or "
            "the trailing slash."
        )
    if status == 429:
        return "Search Console rate limit reached. Retry shortly."
    return f"Search Console API error ({status}): {body[:300]}"


def empty_property_list_message(mode: AuthMode, identity: str | None) -> str:
    """The most common service account failure deserves its own sentence."""
    if mode == "service_account":
        who = identity or "the service account email"
        return (
            f"This service account has not been added to any property yet. "
            f"In Search Console, open each property, go to Settings, Users "
            f"and permissions, Add user, and add {who} with Full or "
            f"Restricted access. Properties you can see in the Search Console "
            f"UI stay invisible to the server until you do this."
        )
    who = identity or "this Google account"
    return (
        f"{who} has no Search Console properties. Add and verify a property "
        "in Search Console first, or sign in with a different account using "
        "`gsc-mcp-server auth`."
    )
