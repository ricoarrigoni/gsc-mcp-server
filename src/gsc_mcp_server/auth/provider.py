"""The auth seam.

Both Google flows converge on `google.auth.credentials.Credentials`, so this
protocol is thin on purpose. Nothing downstream, not the HTTP client, not the
tools, not the server, ever learns which mode it got.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from google.auth.credentials import Credentials

from ..config import AuthMode


@runtime_checkable
class AuthProvider(Protocol):
    def credentials(self) -> Credentials:
        """Return valid credentials, refreshing if needed."""
        ...

    def mode(self) -> AuthMode:
        """"oauth" or "service_account". Used in logs and error messages."""
        ...

    def identity(self) -> str | None:
        """Email of the account or service account, when known."""
        ...

    def granted_scopes(self) -> tuple[str, ...]:
        """Scopes actually granted, for the startup read-only assertion."""
        ...
