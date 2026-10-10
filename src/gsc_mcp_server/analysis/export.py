"""Write Search Analytics rows to CSV for export_query.

The rows go to disk and only the path comes back, so a large pull never
enters the model's context. Files are created owner-only.
"""

from __future__ import annotations

import csv
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

METRIC_COLUMNS = ("clicks", "impressions", "ctr", "position")

# Search queries are typed by strangers. A query such as =HYPERLINK(...) would
# run as a formula when the CSV is opened in a spreadsheet, so text cells
# starting with a formula trigger get a leading apostrophe (OWASP guidance).
_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(value: str) -> str:
    return f"'{value}" if value.startswith(_FORMULA_TRIGGERS) else value


def write_rows_csv(
    path: Path, dimensions: list[str], pages: Iterable[list[dict[str, Any]]]
) -> int:
    """Stream pages into `path`. Returns the number of data rows written.

    Writes to a temporary file first, so a failed pull never leaves a
    truncated CSV that looks complete.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    tmp = path.with_suffix(path.suffix + ".partial")
    count = 0
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow([*dimensions, *METRIC_COLUMNS])
            for page in pages:
                for row in page:
                    keys = [_safe_cell(str(k)) for k in row.get("keys") or []]
                    position = row.get("position")
                    writer.writerow(
                        [
                            *keys,
                            int(row.get("clicks", 0)),
                            int(row.get("impressions", 0)),
                            round(float(row.get("ctr", 0.0)), 6),
                            # Absent for discover and googleNews: blank, not 0.
                            "" if position is None else round(float(position), 2),
                        ]
                    )
                    count += 1
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return count
