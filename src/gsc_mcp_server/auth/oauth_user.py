"""OAuth user flow: you sign in, the server keeps a refresh token.

The 7-day trap: a Google OAuth app left in Testing status expires every
refresh token after seven days. Publish the consent screen to In production.
See docs/setup-oauth.md.
"""

from __future__ import annotations

import logging
import threading

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from ..config import AuthMode, Config
from ..constants import OAUTH_SCOPES
from ..errors import AuthNotConfiguredError, TokenError
from .token_store import TokenStore

logger = logging.getLogger(__name__)


class OAuthUserProvider:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        # Tools run in worker threads; one refresh at a time.
        self._lock = threading.Lock()
        self._store = TokenStore(cfg.state_dir)
        self._creds: Credentials | None = None

    def mode(self) -> AuthMode:
        return "oauth"

    def identity(self) -> str | None:
        payload = self._store.load()
        return (payload or {}).get("account_email")

    def granted_scopes(self) -> tuple[str, ...]:
        creds = self._load()
        return tuple(creds.scopes or ())

    def credentials(self) -> Credentials:
        with self._lock:
            return self._fresh_credentials()

    def _fresh_credentials(self) -> Credentials:
        creds = self._load()
        if not creds.valid:
            try:
                creds.refresh(Request())
            except Exception as exc:
                raise TokenError.for_mode("oauth") from exc
            self._persist(creds)
        return creds

    # --- interactive setup, called by `gsc-mcp-server auth` ---------------
    def run_login_flow(self) -> Credentials:
        from google_auth_oauthlib.flow import InstalledAppFlow

        path = self._cfg.oauth_client_secret
        if path is None or not path.exists():
            raise AuthNotConfiguredError(
                "No OAuth client file found. Set GSC_OAUTH_CLIENT_SECRET to "
                "the client_secret JSON you downloaded from Google Cloud "
                "Console. See docs/setup-oauth.md."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(path), scopes=list(OAUTH_SCOPES)
        )
        # Loopback redirect. port=0 lets the OS pick a free port.
        creds = flow.run_local_server(port=0, prompt="consent")
        self._creds = creds
        self._persist(creds, fetch_email=True)
        return creds

    def logout(self) -> None:
        self._store.clear()
        self._creds = None

    # --- internals ---------------------------------------------------------
    def _load(self) -> Credentials:
        if self._creds is not None:
            return self._creds

        payload = self._store.load()
        if not payload:
            raise AuthNotConfiguredError(
                "Not signed in yet. Run `gsc-mcp-server auth`."
            )

        self._creds = Credentials(
            token=payload.get("token"),
            refresh_token=payload.get("refresh_token"),
            token_uri=payload.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=payload.get("client_id"),
            client_secret=payload.get("client_secret"),
            scopes=payload.get("scopes") or list(OAUTH_SCOPES),
        )
        return self._creds

    def _persist(self, creds: Credentials, fetch_email: bool = False) -> None:
        payload = self._store.load() or {}
        payload.update(
            {
                "token": creds.token,
                "refresh_token": creds.refresh_token or payload.get("refresh_token"),
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": list(creds.scopes or OAUTH_SCOPES),
            }
        )
        if fetch_email:
            payload["account_email"] = _fetch_account_email(creds)
        self._store.save(payload)


def _fetch_account_email(creds: Credentials) -> str | None:
    """Best effort. Used only for the startup line and error messages."""
    try:
        import httpx

        from ..constants import USERINFO_URL

        resp = httpx.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {creds.token}"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            value = resp.json().get("email")
            return value if isinstance(value, str) else None
    except Exception as exc:  # pragma: no cover
        logger.debug("userinfo lookup failed: %s", exc)
    return None
