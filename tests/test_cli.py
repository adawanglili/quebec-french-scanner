"""Report file naming: scans must never silently replace an earlier report."""

from __future__ import annotations

from datetime import datetime

from qfscan.__main__ import default_report_name, report_path


def test_default_name_uses_site_and_time():
    when = datetime(2026, 10, 19, 16, 44)
    assert default_report_name("https://www.canada.ca/fr.html", when) == "canada.ca_2026-10-19_1644.json"
    assert default_report_name("https://yuanqi.ca/", when) == "yuanqi.ca_2026-10-19_1644.json"
    assert default_report_name("http://127.0.0.1:8000/", when) == "127.0.0.1-8000_2026-10-19_1644.json"


def test_existing_report_is_not_replaced(tmp_path):
    first = tmp_path / "site1.json"
    first.write_text("{}")
    second = report_path("https://x.ca/", str(first))
    assert second.name == "site1_2.json"
    second.write_text("{}")
    assert report_path("https://x.ca/", str(first)).name == "site1_3.json"


def test_overwrite_flag_replaces(tmp_path):
    first = tmp_path / "site1.json"
    first.write_text("{}")
    assert report_path("https://x.ca/", str(first), overwrite=True) == first


def test_missing_json_suffix_is_added(tmp_path):
    assert report_path("https://x.ca/", str(tmp_path / "site1")).name == "site1.json"
