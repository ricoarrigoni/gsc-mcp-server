#!/usr/bin/env python3
"""Fail if any tracked file contains a domain that is not an example domain.

A public repository must never ship real property data. Fixtures, docs and
examples use example.com / example.org only.
"""

from __future__ import annotations

import re
import subprocess
import sys

ALLOWED = {
    "example.com",
    "example.org",
    "example.net",
    "www.example.com",
    "localhost",
}

# Hosts that are legitimately referenced in config, docs and code.
ALLOWED_HOSTS = {
    "googleapis.com",
    "www.googleapis.com",
    "searchconsole.googleapis.com",
    "accounts.google.com",
    "oauth2.googleapis.com",
    "openidconnect.googleapis.com",
    "console.cloud.google.com",
    "search.google.com",
    "developers.google.com",
    "support.google.com",
    "github.com",
    "pypi.org",
    "docs.astral.sh",
    "astral.sh",
    "modelcontextprotocol.io",
    "py.sdk.modelcontextprotocol.io",
    "blog.modelcontextprotocol.io",
    "claude.ai",
    "pre-commit.com",
    "schema.org",
}

SKIP_PREFIXES = ("tests/fixtures/golden/",)
SKIP_SUFFIXES = (".lock", ".png", ".jpg", ".gif", ".svg", ".ico")

DOMAIN_RE = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:com|org|net|io|de|es|pt|co|uk|ai|dev|app|info|biz|eu|ch)\b",
    re.IGNORECASE,
)


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    )
    return [f for f in out.stdout.splitlines() if f]


def main() -> int:
    findings: list[tuple[str, int, str]] = []
    for path in tracked_files():
        if path.startswith(SKIP_PREFIXES) or path.endswith(SKIP_SUFFIXES):
            continue
        if path == "scripts/check_no_real_domains.py":
            continue
        try:
            text = open(path, encoding="utf-8").read()
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in DOMAIN_RE.findall(line):
                host = match.lower()
                if host in ALLOWED or host in ALLOWED_HOSTS:
                    continue
                if any(host.endswith("." + a) for a in ALLOWED):
                    continue
                findings.append((path, lineno, host))

    if findings:
        print("Real domains found. A public repo must use example.com only.\n")
        for path, lineno, host in findings:
            print(f"  {path}:{lineno}  {host}")
        print(
            "\nIf a host is legitimate (a Google API endpoint, a docs link), "
            "add it to ALLOWED_HOSTS in scripts/check_no_real_domains.py."
        )
        return 1

    print(f"OK: no real domains in {len(tracked_files())} tracked files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
