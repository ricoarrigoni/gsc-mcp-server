"""Configuration, read from the environment.

One auth-mode value, explicit, with inference when unset. Inference is a
convenience; the startup log line always states the mode that was chosen, so
it is never a silent surprise.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

AuthMode = Literal["oauth", "service_account"]


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip()
    return Path(raw).expanduser() if raw else None


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_list(name: str) -> tuple[str, ...]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


@dataclass(frozen=True)
class Config:
    auth_mode: AuthMode
    oauth_client_secret: Path | None = None
    service_account_key: Path | None = None
    property_allowlist: tuple[str, ...] = field(default_factory=tuple)
    redact_pii: bool = False
    state_dir: Path = field(default_factory=lambda: Path.home() / ".gsc-mcp")
    export_dir: Path | None = None

    @classmethod
    def from_env(cls) -> Config:
        client_secret = _env_path("GSC_OAUTH_CLIENT_SECRET")
        key_path = _env_path("GSC_SERVICE_ACCOUNT_KEY")

        declared = os.environ.get("GSC_AUTH_MODE", "").strip().lower()
        if declared in {"oauth", "service_account"}:
            mode: AuthMode = declared  # type: ignore[assignment]
        elif key_path is not None:
            mode = "service_account"
        else:
            mode = "oauth"

        state_dir = _env_path("GSC_STATE_DIR") or (Path.home() / ".gsc-mcp")

        return cls(
            auth_mode=mode,
            oauth_client_secret=client_secret,
            service_account_key=key_path,
            property_allowlist=_env_list("GSC_PROPERTY_ALLOWLIST"),
            redact_pii=_env_bool("GSC_REDACT_PII", False),
            state_dir=state_dir,
            export_dir=_env_path("GSC_EXPORT_DIR"),
        )

    @property
    def exports_path(self) -> Path:
        """Where export_query writes CSVs. Outside any repo by default."""
        return self.export_dir or (self.state_dir / "exports")

    def allows(self, site_url: str) -> bool:
        """An empty allowlist allows everything. siteUrl is matched verbatim."""
        return not self.property_allowlist or site_url in self.property_allowlist
