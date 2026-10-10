import logging

from gsc_mcp_server.logging_setup import RedactingFilter


def record(message: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="t", level=logging.INFO, pathname="", lineno=0,
        msg=message, args=(), exc_info=None,
    )


def apply(message: str) -> str:
    rec = record(message)
    RedactingFilter().filter(rec)
    return rec.getMessage()


def test_bearer_tokens_are_redacted():
    assert "ya29" not in apply("Authorization: Bearer ya29.A0ARrdaM-notreal")


def test_refresh_tokens_are_redacted():
    out = apply('{"refresh_token": "1//0gLongLookingTokenValue"}')
    assert "0gLongLookingTokenValue" not in out


def test_client_secret_is_redacted():
    out = apply('client_secret=GOCSPX-abcdefghijklmno')
    assert "GOCSPX-abcdefghijklmno" not in out


def test_ordinary_messages_are_untouched():
    msg = "query_performance sc-domain:example.com 2026-09-01..2026-09-28 120 rows"
    assert apply(msg) == msg
