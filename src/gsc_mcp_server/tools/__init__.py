"""MCP tool registration.

Keep the tool count at nine or fewer. Every tool definition sits in the
model's context on every turn, so an unused tool is a permanent token cost.

Each module exposes `register(server, context)`.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def register_all(server, context) -> None:
    from . import performance, properties, urls

    modules = [properties, performance, urls]
    # TODO: add sitemaps.
    for module in modules:
        module.register(server, context)
    logger.info("registered %d tool module(s)", len(modules))
