import pytest

from gsc_mcp_server.auth.factory import assert_read_only
from gsc_mcp_server.config import Config
from gsc_mcp_server.constants import SCOPE_READONLY, SCOPE_WRITE
from gsc_mcp_server.errors import ScopeTooWideError, empty_property_list_message


class FakeProvider:
    def __init__(self, scopes, mode="oauth", identity="user@example.com"):
        self._scopes = tuple(scopes)
        self._mode = mode
        self._identity = identity

    def credentials(self):
        raise NotImplementedError

    def mode(self):
        return self._mode

    def identity(self):
        return self._identity

    def granted_scopes(self):
        return self._scopes


def test_read_only_scope_passes():
    assert_read_only(FakeProvider([SCOPE_READONLY]))


def test_write_scope_is_refused():
    with pytest.raises(ScopeTooWideError, match="read-only by design"):
        assert_read_only(FakeProvider([SCOPE_READONLY, SCOPE_WRITE]))


def test_missing_read_scope_is_refused():
    with pytest.raises(ScopeTooWideError, match="does not grant"):
        assert_read_only(FakeProvider(["openid"]))


def test_mode_is_inferred_from_the_key_path(monkeypatch, tmp_path):
    monkeypatch.delenv("GSC_AUTH_MODE", raising=False)
    monkeypatch.setenv("GSC_SERVICE_ACCOUNT_KEY", str(tmp_path / "key.json"))
    assert Config.from_env().auth_mode == "service_account"


def test_mode_defaults_to_oauth(monkeypatch):
    monkeypatch.delenv("GSC_AUTH_MODE", raising=False)
    monkeypatch.delenv("GSC_SERVICE_ACCOUNT_KEY", raising=False)
    assert Config.from_env().auth_mode == "oauth"


def test_explicit_mode_beats_inference(monkeypatch, tmp_path):
    monkeypatch.setenv("GSC_AUTH_MODE", "oauth")
    monkeypatch.setenv("GSC_SERVICE_ACCOUNT_KEY", str(tmp_path / "key.json"))
    assert Config.from_env().auth_mode == "oauth"


def test_allowlist_matches_site_url_verbatim(monkeypatch):
    monkeypatch.setenv("GSC_PROPERTY_ALLOWLIST", "sc-domain:example.com")
    cfg = Config.from_env()
    assert cfg.allows("sc-domain:example.com")
    # A URL-prefix property is a different property, not the same one.
    assert not cfg.allows("https://example.com/")


def test_empty_allowlist_allows_everything(monkeypatch):
    monkeypatch.delenv("GSC_PROPERTY_ALLOWLIST", raising=False)
    assert Config.from_env().allows("sc-domain:example.com")


def test_service_account_empty_list_message_names_the_email():
    message = empty_property_list_message(
        "service_account", "gsc-reader@proj.iam.gserviceaccount.com"
    )
    assert "gsc-reader@proj.iam.gserviceaccount.com" in message
    assert "Users and permissions" in message


def test_oauth_empty_list_message_does_not_mention_adding_a_user():
    message = empty_property_list_message("oauth", "user@example.com")
    assert "Users and permissions" not in message
