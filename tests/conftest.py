"""Drive tools through a real MCPServer against a mocked Google API.

Tools are registered on the installed SDK's MCPServer and called with
`call_tool`, so the tests cover registration, argument validation and the
result shape, not just the function body.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from mcp.server import MCPServer

from gsc_mcp_server.config import Config
from gsc_mcp_server.gsc.client import GscClient

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


class FakeCreds:
    token = "test-token"


class FakeAuth:
    def __init__(self, mode: str = "oauth", identity: str = "user@example.com"):
        self._mode = mode
        self._identity = identity

    def credentials(self):
        return FakeCreds()

    def mode(self):
        return self._mode

    def identity(self):
        return self._identity

    def granted_scopes(self):
        return ("https://www.googleapis.com/auth/webmasters.readonly",)


class FakeContext:
    def __init__(self, cfg: Config, handler: Callable[[httpx.Request], Any]):
        self.config = cfg
        self.auth = FakeAuth()
        self.client = GscClient(
            self.auth, client=httpx.Client(transport=httpx.MockTransport(handler))
        )


class Harness:
    """A server plus a record of every request the tools sent to Google."""

    def __init__(self, tmp_path: Path) -> None:
        self.requests: list[httpx.Request] = []
        self.responses: list[httpx.Response] = []
        self.default = httpx.Response(200, json={})
        self.tmp_path = tmp_path

    def queue(self, *responses: httpx.Response | dict[str, Any]) -> None:
        for r in responses:
            self.responses.append(
                r if isinstance(r, httpx.Response) else httpx.Response(200, json=r)
            )

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responses.pop(0) if self.responses else self.default

    def bodies(self) -> list[dict[str, Any]]:
        return [json.loads(r.content) for r in self.requests if r.content]

    def server(self, **cfg: Any) -> MCPServer:
        from gsc_mcp_server.tools import register_all

        cfg.setdefault("auth_mode", "oauth")
        cfg.setdefault("state_dir", self.tmp_path / "state")
        self.context = FakeContext(Config(**cfg), self._handle)
        server = MCPServer(name="test")
        register_all(server, self.context)
        return server

    async def call(self, server: MCPServer, name: str, **args: Any):
        return await server.call_tool(name, args)


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    return Harness(tmp_path)
