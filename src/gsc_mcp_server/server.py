"""MCP server assembly.

Builds the context every tool shares (config, auth, the read-only scope
assertion, the HTTP client) once at startup, then registers the tool
modules from tools/. Nothing here imports googleapiclient or talks to
Google directly; everything goes through gsc/client.py.
"""

from __future__ import annotations

import logging

from .auth import assert_read_only, build_auth_provider
from .config import Config
from .gsc import GscClient

logger = logging.getLogger(__name__)


class ServerContext:
    """What every tool needs, built once at startup."""

    def __init__(self, cfg: Config) -> None:
        self.config = cfg
        self.auth = build_auth_provider(cfg)
        assert_read_only(self.auth)
        self.client = GscClient(self.auth)

    def log_startup(self) -> None:
        # A2: always say which mode is actually running. Most "it does not
        # work" reports are someone running the mode they did not expect.
        identity = self.auth.identity() or "identity unknown"
        logger.info("auth: %s (%s)", self.auth.mode(), identity)
        if self.config.property_allowlist:
            logger.info(
                "property allowlist active: %d propert%s",
                len(self.config.property_allowlist),
                "y" if len(self.config.property_allowlist) == 1 else "ies",
            )
        if self.config.redact_pii:
            logger.info("PII redaction filter enabled")


def build_server(cfg: Config):
    """Create and populate the MCP server.

    The import is local so `--help` and `doctor` do not pay for it.
    """
    from mcp.server import MCPServer

    context = ServerContext(cfg)
    context.log_startup()

    server = MCPServer(name="gsc-mcp-server")

    from .tools import register_all

    register_all(server, context)
    return server


def run_stdio(cfg: Config) -> None:
    server = build_server(cfg)
    server.run(transport="stdio")
