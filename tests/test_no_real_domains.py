"""Guard for the public repo: no real domain may ship.

This mirrors the pre-commit hook so a failure shows up in CI too.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_repo_contains_no_real_domains():
    result = subprocess.run(
        [sys.executable, "scripts/check_no_real_domains.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
