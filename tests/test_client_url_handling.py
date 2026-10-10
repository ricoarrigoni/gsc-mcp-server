import httpx
import pytest

from gsc_mcp_server.errors import ApiError, NetworkError
from gsc_mcp_server.gsc.client import GscClient, _redact_url


class FakeCreds:
    token = "test-token"


class FakeProvider:
    def credentials(self):
        return FakeCreds()

    def mode(self):
        return "service_account"

    def identity(self):
        return "gsc-reader@proj.iam.gserviceaccount.com"

    def granted_scopes(self):
        return ("https://www.googleapis.com/auth/webmasters.readonly",)


def client_with(handler) -> GscClient:
    transport = httpx.MockTransport(handler)
    return GscClient(FakeProvider(), client=httpx.Client(transport=transport))


def test_sc_domain_site_url_is_encoded_not_normalised():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"rows": []})

    client_with(handler).query_search_analytics(
        "sc-domain:example.com", {"startDate": "2026-09-01", "endDate": "2026-09-02"}
    )
    assert "sc-domain%3Aexample.com" in seen[0]


def test_url_prefix_site_url_is_encoded_whole():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"rows": []})

    client_with(handler).query_search_analytics(
        "https://example.com/", {"startDate": "2026-09-01", "endDate": "2026-09-02"}
    )
    assert "https%3A%2F%2Fexample.com%2F" in seen[0]


def test_403_message_is_service_account_specific():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    with pytest.raises(ApiError) as exc:
        client_with(handler).list_sites()
    assert "Users and permissions" in str(exc.value)
    assert "gsc-reader@proj.iam.gserviceaccount.com" in str(exc.value)


def test_404_message_mentions_the_verbatim_site_url_trap():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    with pytest.raises(ApiError, match="sc-domain"):
        client_with(handler).list_sites()


def test_redacted_url_hides_the_property():
    url = (
        "https://www.googleapis.com/webmasters/v3/sites/"
        "sc-domain%3Aexample.com/searchAnalytics/query"
    )
    assert "example.com" not in _redact_url(url)


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr("gsc_mcp_server.gsc.client.time.sleep", lambda _: None)


def test_network_errors_are_retried_then_mapped(no_sleep):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(NetworkError, match="Could not reach Google") as exc:
        client_with(handler).list_sites()
    assert len(calls) == 4
    assert exc.value.reason == "network_error"


def test_a_transient_network_error_recovers(no_sleep):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("reset", request=request)
        return httpx.Response(200, json={"siteEntry": []})

    assert client_with(handler).list_sites() == []
    assert len(calls) == 2


def test_non_json_success_is_an_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>oops</html>")

    with pytest.raises(ApiError, match="not JSON"):
        client_with(handler).list_sites()
