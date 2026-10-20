"""Local scan page: run a scan through the page and protect the reports folder."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from qfscan.server import make_handler


@pytest.fixture()
def server(tmp_path):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(tmp_path))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", tmp_path
    httpd.shutdown()


def post(url, data):
    req = urllib.request.Request(url, json.dumps(data).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_scan_through_the_page(server, fixture_url):
    base, reports = server
    code, job = post(base + "/scan", {"url": fixture_url, "brands": ["Northwind"], "max_pages": 50})
    assert code == 202
    for _ in range(120):
        status = json.load(urllib.request.urlopen(f"{base}/status/{job['id']}"))
        if status["state"] in ("done", "failed"):
            break
        time.sleep(0.5)
    assert status["state"] == "done", status
    assert (reports / status["report"]).exists()
    home = urllib.request.urlopen(base + "/").read().decode()
    assert status["report"] in home


def test_rejects_bad_address(server):
    base, _ = server
    code, body = post(base + "/scan", {"url": "file:///etc/passwd"})
    assert code == 400 and "http" in body["error"]


@pytest.mark.parametrize("path", ["/reports/../pyproject.toml", "/reports/%2e%2e%2fpyproject.toml", "/reports/x.py"])
def test_only_report_files_are_served(server, path):
    base, _ = server
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(base + path)
    assert err.value.code == 404
