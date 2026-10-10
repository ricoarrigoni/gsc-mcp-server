import json
import os
import stat
from datetime import date

from gsc_mcp_server.gsc.quota import STATE_FILE, InspectionQuota

SITE = "sc-domain:example.com"


def test_refuses_at_the_soft_cap(tmp_path):
    quota = InspectionQuota(tmp_path, soft_cap=2, today=lambda: date(2026, 10, 1))
    assert quota.try_reserve(SITE)
    assert quota.try_reserve(SITE)
    assert not quota.try_reserve(SITE)
    assert quota.used(SITE) == 2


def test_counts_are_per_property(tmp_path):
    quota = InspectionQuota(tmp_path, soft_cap=1, today=lambda: date(2026, 10, 1))
    assert quota.try_reserve(SITE)
    assert quota.try_reserve("https://example.com/")


def test_count_survives_a_restart_and_resets_next_day(tmp_path):
    day = {"value": date(2026, 10, 1)}
    InspectionQuota(tmp_path, soft_cap=1, today=lambda: day["value"]).try_reserve(SITE)

    again = InspectionQuota(tmp_path, soft_cap=1, today=lambda: day["value"])
    assert not again.try_reserve(SITE)

    day["value"] = date(2026, 10, 2)
    assert again.try_reserve(SITE)


def test_state_file_is_owner_only(tmp_path):
    InspectionQuota(tmp_path, today=lambda: date(2026, 10, 1)).try_reserve(SITE)
    path = tmp_path / STATE_FILE
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert json.loads(path.read_text())["counts"] == {SITE: 1}


def test_corrupt_state_file_starts_from_zero(tmp_path):
    (tmp_path / STATE_FILE).write_text("{not json")
    quota = InspectionQuota(tmp_path, soft_cap=1, today=lambda: date(2026, 10, 1))
    assert quota.try_reserve(SITE)
