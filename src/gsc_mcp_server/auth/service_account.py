"""Service account flow: a key file, no browser, no consent screen.

Access does not follow any human account. Each property must have the service
account email added as a user in Search Console, or sites.list comes back
empty. See docs/setup-service-account.md.
"""

from __future__ import annotations

import json
import os
import stat
import threading

from google.auth.transport.requests import Request
from google.oauth2 import service_account

from ..config import AuthMode, Config
from ..constants import SERVICE_ACCOUNT_SCOPES
from ..errors import AuthNotConfiguredError, TokenError


class ServiceAccountProvider:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        # Tools run in worker threads; one refresh at a time.
        self._lock = threading.Lock()
        self._creds: service_account.Credentials | None = None
        self._email: str | None = None

    def mode(self) -> AuthMode:
        return "service_account"

    def identity(self) -> str | None:
        if self._email is None:
            self._load()
        return self._email

    def granted_scopes(self) -> tuple[str, ...]:
        return tuple(SERVICE_ACCOUNT_SCOPES)

    def credentials(self) -> service_account.Credentials:
        with self._lock:
            return self._fresh_credentials()

    def _fresh_credentials(self) -> service_account.Credentials:
        creds = self._load()
        if not creds.valid:
            try:
                creds.refresh(Request())
            except Exception as exc:
                raise TokenError.for_mode("service_account") from exc
        return creds

    def key_permissions_warning(self) -> str | None:
        """Return a warning if the key file is readable by others."""
        path = self._cfg.service_account_key
        if path is None or not path.exists():
            return None
        mode = stat.S_IMODE(os.stat(path).st_mode)
        if mode & 0o077:
            return (
                f"The key file {path} is readable by other users "
                f"(mode {mode:o}). Run: chmod 600 {path}"
            )
        return None

    # --- internals ---------------------------------------------------------
    def _load(self) -> service_account.Credentials:
        if self._creds is not None:
            return self._creds

        path = self._cfg.service_account_key
        if path is None or not path.exists():
            raise AuthNotConfiguredError(
                "No service account key found. Set GSC_SERVICE_ACCOUNT_KEY to "
                "the JSON key path. See docs/setup-service-account.md."
            )

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AuthNotConfiguredError(
                f"{path} is not valid JSON. Re-download the key from Google "
                "Cloud Console."
            ) from exc

        if raw.get("type") != "service_account":
            raise AuthNotConfiguredError(
                f"{path} is not a service account key (type is "
                f"{raw.get('type')!r}). In Google Cloud Console, open the "
                "service account, Keys, Add key, JSON."
            )

        self._email = raw.get("client_email")
        self._creds = service_account.Credentials.from_service_account_info(
            raw, scopes=list(SERVICE_ACCOUNT_SCOPES)
        )
        return self._creds
