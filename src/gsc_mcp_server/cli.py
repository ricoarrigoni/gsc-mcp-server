"""Command line entry point: auth, doctor, serve."""

from __future__ import annotations

import argparse
import logging
import sys

from . import logging_setup
from .auth import build_auth_provider
from .auth.oauth_user import OAuthUserProvider
from .auth.service_account import ServiceAccountProvider
from .config import Config
from .doctor import FAIL, OK, WARN, run_doctor

logger = logging.getLogger(__name__)

_SYMBOL = {OK: "PASS", WARN: "WARN", FAIL: "FAIL"}


def cmd_auth(cfg: Config) -> int:
    provider = build_auth_provider(cfg)

    if isinstance(provider, OAuthUserProvider):
        print("Opening a browser to sign in to Google...")
        provider.run_login_flow()
        print(f"Signed in as {provider.identity() or 'unknown account'}.")
        print(
            "\nIf this stops working in about a week, your OAuth app is "
            "still in Testing status. Publish the consent screen to "
            "'In production' in Google Cloud Console. See docs/setup-oauth.md."
        )
        return 0

    if isinstance(provider, ServiceAccountProvider):
        email = provider.identity()
        warning = provider.key_permissions_warning()
        if warning:
            print(f"WARNING: {warning}\n")
        print(f"Service account key loaded.\n\n  {email}\n")
        print(
            "Add that email as a user on every property you want to read:\n"
            "  Search Console -> the property -> Settings ->\n"
            "  Users and permissions -> Add user -> paste the email ->\n"
            "  permission Full or Restricted.\n\n"
            "Until you do, `gsc-mcp-server doctor` will report zero "
            "properties even for sites you can see in the Search Console UI."
        )
        return 0

    print("Unknown auth mode.", file=sys.stderr)
    return 1


def cmd_doctor(cfg: Config) -> int:
    checks = run_doctor(cfg)
    width = max(len(c.name) for c in checks)
    failed = 0
    for check in checks:
        if check.status == FAIL:
            failed += 1
        print(f"[{_SYMBOL[check.status]}] {check.name.ljust(width)}  {check.detail}")
    print()
    if failed:
        print(f"{failed} check(s) failed. Fix the first failure and re-run.")
        return 1
    print("All checks passed.")
    return 0


def cmd_serve(cfg: Config) -> int:
    from .server import run_stdio

    run_stdio(cfg)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gsc-mcp-server",
        description="Read-only MCP server for Google Search Console.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("auth", help="Set up whichever auth mode is configured")
    sub.add_parser("doctor", help="Diagnose configuration and access")
    sub.add_parser("serve", help="Run the MCP server over stdio (default)")

    args = parser.parse_args(argv)
    logging_setup.configure(logging.DEBUG if args.verbose else logging.INFO)
    cfg = Config.from_env()

    try:
        if args.command == "auth":
            return cmd_auth(cfg)
        if args.command == "doctor":
            return cmd_doctor(cfg)
        return cmd_serve(cfg)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Run `gsc-mcp-server doctor` for a diagnosis.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
