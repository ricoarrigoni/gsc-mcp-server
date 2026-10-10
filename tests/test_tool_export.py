import csv
import os
import stat

import httpx

SITE = "sc-domain:example.com"


def paged(total: int, *, position: bool = True):
    def responder(body: dict) -> dict:
        start, limit = body.get("startRow", 0), body["rowLimit"]
        rows = []
        for i in range(start, min(start + limit, total)):
            row = {"keys": [f"q{i}"], "clicks": i, "impressions": 10 * i, "ctr": 0.1}
            if position:
                row["position"] = 3.25
            rows.append(row)
        return {"rows": rows}

    return responder


def read_csv(path: str) -> list[dict[str, str]]:
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


async def test_export_writes_csv_and_returns_path_not_rows(harness, tmp_path):
    harness.responder = paged(30)
    server = harness.server(export_dir=tmp_path / "out")

    out = await harness.call(server, "export_query", siteUrl=SITE)

    s = out.structured_content
    assert s["ok"] is True
    assert s["rowCount"] == 30
    assert "rows" not in s
    assert "q1" not in out.content[0].text
    rows = read_csv(s["path"])
    assert list(rows[0]) == ["query", "clicks", "impressions", "ctr", "position"]
    assert len(rows) == 30
    assert stat.S_IMODE(os.stat(s["path"]).st_mode) == 0o600


async def test_export_pages_beyond_the_inline_cap(harness, tmp_path):
    harness.responder = paged(30_000)
    server = harness.server(export_dir=tmp_path)

    out = await harness.call(server, "export_query", siteUrl=SITE, maxRows=27_000)

    bodies = harness.bodies()
    assert [b["rowLimit"] for b in bodies] == [25_000, 2_000]
    assert [b["startRow"] for b in bodies] == [0, 25_000]
    assert out.structured_content["rowCount"] == 27_000
    assert out.structured_content["truncated"] is True


async def test_export_leaves_position_blank_when_absent(harness, tmp_path):
    harness.responder = paged(2, position=False)
    server = harness.server(export_dir=tmp_path)
    out = await harness.call(
        server, "export_query", siteUrl=SITE, searchType="discover"
    )
    rows = read_csv(out.structured_content["path"])
    assert [r["position"] for r in rows] == ["", ""]


async def test_export_neutralises_spreadsheet_formulas(harness, tmp_path):
    harness.queue(
        {"rows": [{"keys": ["=cmd"], "clicks": 1, "impressions": 1, "ctr": 1.0}]}
    )
    server = harness.server(export_dir=tmp_path)
    out = await harness.call(server, "export_query", siteUrl=SITE)
    assert read_csv(out.structured_content["path"])[0]["query"] == "'=cmd"


async def test_failed_export_leaves_no_file(harness, tmp_path):
    harness.queue(httpx.Response(403, text="forbidden"))
    server = harness.server(export_dir=tmp_path / "out")
    out = await harness.call(server, "export_query", siteUrl=SITE)
    assert out.structured_content["ok"] is False
    assert list((tmp_path / "out").glob("*")) == []


async def test_unwritable_export_dir_is_ok_false(harness, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("")
    server = harness.server(export_dir=blocker / "sub")
    out = await harness.call(server, "export_query", siteUrl=SITE)
    assert out.structured_content["reason"] == "io_error"


async def test_export_rejects_half_range_before_any_call(harness, tmp_path):
    server = harness.server(export_dir=tmp_path)
    out = await harness.call(server, "export_query", siteUrl=SITE, endDate="2026-09-01")
    assert out.structured_content["reason"] == "invalid_request"
    assert harness.requests == []


async def test_export_defaults_to_the_state_dir(harness):
    harness.responder = paged(1)
    server = harness.server()
    out = await harness.call(server, "export_query", siteUrl=SITE)
    assert out.structured_content["path"].startswith(
        str(harness.tmp_path / "state" / "exports")
    )
