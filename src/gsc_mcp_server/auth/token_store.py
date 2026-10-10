"""Where the OAuth refresh token lives.

OS keyring by default. An encrypted-at-rest file is not attempted here: if the
keyring is unavailable, the fallback is a 0600 file in the state directory,
and the README says plainly that this is less safe.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

SERVICE_NAME = "gsc-mcp-server"
ACCOUNT_NAME = "oauth-token"


class TokenStore:
    def __init__(self, state_dir: Path) -> None:
        self._state_dir = state_dir
        self._file = state_dir / "token.json"

    # --- keyring -----------------------------------------------------------
    def _keyring(self):
        try:
            import keyring

            # Some backends import fine but fail on use. Probe cheaply.
            keyring.get_keyring()
            return keyring
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.debug("keyring unavailable: %s", exc)
            return None

    # --- public API --------------------------------------------------------
    def load(self) -> dict | None:
        kr = self._keyring()
        if kr is not None:
            try:
                raw = kr.get_password(SERVICE_NAME, ACCOUNT_NAME)
                if raw:
                    return json.loads(raw)
            except Exception as exc:  # pragma: no cover
                logger.debug("keyring read failed: %s", exc)

        if self._file.exists():
            return json.loads(self._file.read_text(encoding="utf-8"))
        return None

    def save(self, payload: dict) -> str:
        """Persist the token. Returns "keyring" or the file path, for logging."""
        raw = json.dumps(payload)
        kr = self._keyring()
        if kr is not None:
            try:
                kr.set_password(SERVICE_NAME, ACCOUNT_NAME, raw)
                return "keyring"
            except Exception as exc:  # pragma: no cover
                logger.debug("keyring write failed: %s", exc)

        self._state_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self._state_dir, 0o700)
        self._file.write_text(raw, encoding="utf-8")
        os.chmod(self._file, 0o600)
        return str(self._file)

    def clear(self) -> None:
        kr = self._keyring()
        if kr is not None:
            try:
                kr.delete_password(SERVICE_NAME, ACCOUNT_NAME)
            except Exception as exc:  # pragma: no cover
                logger.debug("keyring delete failed: %s", exc)
        self._file.unlink(missing_ok=True)
