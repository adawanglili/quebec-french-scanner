"""A small local web page for running scans without the command line.

Run:
    python -m qfscan serve

It opens http://127.0.0.1:8765 in your browser. The page only listens on
your own computer. Scans run one at a time in the background, and each
report is saved in the reports folder like a command line scan.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
import uuid
import webbrowser
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .checks import run_checks
from .crawl import DEFAULT_MAX_PAGES, crawl
from .files import scan_saved_pages
from .html import CSS as REPORT_CSS
from .html import render_html, write_sheet
from .report import build_report

HOST = "127.0.0.1"
PORT = 8765
SERVED_SUFFIXES = {".html": "text/html; charset=utf-8", ".csv": "text/csv; charset=utf-8",
                   ".json": "application/json; charset=utf-8"}

MAX_UPLOAD_BYTES = 80 * 1024 * 1024
JOBS: dict[str, dict] = {}
JOB_LOCK = threading.Lock()


def run_job(job_id: str, url: str, brands: list[str], max_pages: int, reports_dir: Path,
            saved_pages: list[tuple[str, str]] | None = None) -> None:
    from .__main__ import report_path, scan_failure_message  # avoid a circular import

    job = JOBS[job_id]

    def progress(done: int, limit: int, page_url: str) -> None:
        job.update(message=f"Crawling page {done} of up to {limit}", detail=page_url)

    try:
        if saved_pages is not None:
            job.update(state="running", message=f"Reading {len(saved_pages)} saved pages")
            result = scan_saved_pages(saved_pages)
            url = result.start_url
        else:
            job.update(state="running", message="Starting the crawl")
            result = crawl(url, max_pages=max_pages, progress=progress)
        if not any(p.status == 200 for p in result.pages.values()):
            job.update(state="failed", message=scan_failure_message(result))
            return
        job.update(message="Checking the French pages", detail="")
        report = build_report(result, run_checks(result, brands=brands or None))
        if saved_pages is not None:
            report["source"] = "saved_pages"
        reports_dir.mkdir(parents=True, exist_ok=True)
        out = report_path(url, str(reports_dir / default_name(url)))
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        out.with_suffix(".html").write_text(render_html(report), encoding="utf-8")
        write_sheet(report, out.with_name(out.stem + "-review.csv"))
        s = report["summary"]
        job.update(state="done", report=out.with_suffix(".html").name,
                   message=f"Done. {s['pages_crawled']} pages, {s['findings']} findings, "
                           f"{s['needs_review']} needs review.")
    except Exception as error:  # show the problem on the page instead of failing silently
        job.update(state="failed", message=f"Scan failed: {error.__class__.__name__}: {error}")


def local_time(stamp: str) -> str:
    try:
        return datetime.fromisoformat(stamp).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return stamp[:16]


def default_name(url: str) -> str:
    from .__main__ import default_report_name
    return default_report_name(url)


def list_reports(reports_dir: Path) -> list[dict]:
    rows = []
    for path in sorted(reports_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            s = report["summary"]
        except (ValueError, KeyError, OSError):
            continue
        html_path = path.with_suffix(".html")
        if not html_path.exists():  # older scans: build the readable report now
            try:
                html_path.write_text(render_html(report), encoding="utf-8")
                write_sheet(report, path.with_name(path.stem + "-review.csv"))
            except (KeyError, OSError):
                pass
        rows.append({
            "name": path.stem,
            "site": urlsplit(report.get("start_url", "")).netloc,
            "when": local_time(report.get("scanned_at", "")),
            "findings": s.get("findings", 0),
            "review": s.get("needs_review", 0),
            "pages": s.get("pages_crawled", 0),
            "has_html": path.with_suffix(".html").exists(),
            "has_csv": path.with_name(path.stem + "-review.csv").exists(),
        })
    return rows


PAGE_CSS = REPORT_CSS + """
form { display:grid; gap:12px; background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px; }
label { display:grid; gap:4px; font-weight:600; font-size:.9rem; }
label small { font-weight:normal; color:var(--muted); }
input { font:inherit; padding:8px 10px; border:1px solid var(--line); border-radius:8px; background:var(--bg); color:var(--ink); }
.row2 { display:grid; grid-template-columns:1fr 160px; gap:12px; }
@media (max-width:560px) { .row2 { grid-template-columns:1fr; } }
button.go { font:inherit; font-weight:600; background:var(--accent); color:#fff; border:0; border-radius:8px;
  padding:10px 16px; cursor:pointer; justify-self:start; }
button.go:disabled { opacity:.5; cursor:default; }
#status { margin:14px 0; min-height:1.5em; }
#status .detail { color:var(--muted); font-size:.85rem; word-break:break-all; }
#status.failed { color:var(--warn); }
.empty { color:var(--muted); }
"""


def render_home(reports_dir: Path) -> str:
    rows = list_reports(reports_dir)
    if rows:
        body = "".join(
            "<tr>"
            f"<td>{escape(r['site'])}</td><td>{escape(r['when'])}</td>"
            f"<td>{r['pages']}</td><td>{r['findings']}</td><td>{r['review']}</td>"
            "<td>"
            + (f'<a href="/reports/{escape(r["name"])}.html" target="_blank">Report</a> ' if r["has_html"] else "")
            + (f'· <a href="/reports/{escape(r["name"])}-review.csv">Review sheet</a>' if r["has_csv"] else "")
            + "</td></tr>"
            for r in rows
        )
        table = ("<table><thead><tr><th>Site</th><th>Scanned</th><th>Pages</th><th>Findings</th>"
                 f"<th>Review</th><th>Open</th></tr></thead><tbody>{body}</tbody></table>")
    else:
        table = '<p class="empty">No reports yet.</p>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quebec French Scanner</title>
<style>{PAGE_CSS}</style>
</head>
<body>
<div class="wrap">
<h1>Quebec French Scanner</h1>
<p class="meta">Finds French market fit opportunities on one website, grounded in OQLF sources. It is not legal advice.</p>
<h2>New scan</h2>
<form id="scan">
  <label>Website address <small>Start page, for example https://www.example.ca/fr/</small>
    <input name="url" type="url" required placeholder="https://" autocomplete="url"></label>
  <div class="row2">
    <label>Brand or product names <small>Not counted as English. Separate with commas.</small>
      <input name="brands" placeholder="Northwind, Brew Club"></label>
    <label>Page limit <small>Up to 200</small>
      <input name="max_pages" type="number" min="1" max="200" value="{DEFAULT_MAX_PAGES}"></label>
  </div>
  <button class="go" type="submit">Scan</button>
</form>
<h2>Or scan saved pages</h2>
<p class="muted">For sites that block the scanner. Open each page in your browser, press Ctrl+S and
choose "Webpage, complete". Save the English and French versions. Then pick the saved files or their folder here.</p>
<form id="files">
  <label>Saved pages <small>Pick .html files, or use the folder button</small>
    <input name="pages" type="file" multiple accept=".html,.htm"></label>
  <label>Or a whole folder
    <input name="folder" type="file" webkitdirectory multiple></label>
  <label>Brand or product names <small>Separate with commas.</small>
    <input name="brands" placeholder="Northwind, Brew Club"></label>
  <button class="go" type="submit">Scan saved pages</button>
</form>
<div id="status" role="status" aria-live="polite"></div>
<h2>Reports</h2>
<div id="reports">{table}</div>
</div>
<script>
var form = document.getElementById('scan');
var filesForm = document.getElementById('files');
var statusEl = document.getElementById('status');
var button = form.querySelector('button');
var filesButton = filesForm.querySelector('button');
function busy(on) {{ button.disabled = on; filesButton.disabled = on; }}
function start(route, data) {{
  busy(true);
  fetch(route, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(data) }})
    .then(function (r) {{ return r.json(); }})
    .then(function (job) {{
      if (job.error) {{ show(job.error, '', true); busy(false); return; }}
      poll(job.id);
    }})
    .catch(function () {{ show('Could not reach the scanner. Is it still running?', '', true); busy(false); }});
}}
function brandList(input) {{
  return input.value.split(',').map(function (s) {{ return s.trim(); }}).filter(Boolean);
}}
filesForm.addEventListener('submit', function (e) {{
  e.preventDefault();
  var picked = Array.prototype.slice.call(filesForm.pages.files)
    .concat(Array.prototype.slice.call(filesForm.folder.files))
    .filter(function (f) {{
      var path = (f.webkitRelativePath || f.name).split(String.fromCharCode(92)).join('/');
      return /[.]html?$/i.test(f.name) && path.indexOf('_files/') === -1;
    }});
  if (!picked.length) {{ show('Choose at least one saved .html page.', '', true); return; }}
  show('Reading ' + picked.length + ' saved pages...');
  Promise.all(picked.map(function (f) {{
    return f.text().then(function (t) {{ return {{ name: f.webkitRelativePath || f.name, content: t }}; }});
  }})).then(function (files) {{
    start('/scan-files', {{ files: files, brands: brandList(filesForm.brands) }});
  }});
}});
function show(msg, detail, failed) {{
  statusEl.className = failed ? 'failed' : '';
  statusEl.innerHTML = '';
  var p = document.createElement('div'); p.textContent = msg; statusEl.appendChild(p);
  if (detail) {{ var d = document.createElement('div'); d.className = 'detail'; d.textContent = detail; statusEl.appendChild(d); }}
}}
form.addEventListener('submit', function (e) {{
  e.preventDefault();
  show('Starting the scan...');
  start('/scan', {{
    url: form.url.value.trim(),
    brands: brandList(form.brands),
    max_pages: parseInt(form.max_pages.value, 10) || {DEFAULT_MAX_PAGES}
  }});
}});
function poll(id) {{
  fetch('/status/' + id).then(function (r) {{ return r.json(); }}).then(function (job) {{
    if (job.state === 'done') {{
      show(job.message);
      var a = document.createElement('a'); a.href = '/reports/' + job.report; a.target = '_blank';
      a.textContent = 'Open the report'; statusEl.appendChild(a);
      window.open('/reports/' + job.report, '_blank');
      busy(false);
      fetch('/reports-table').then(function (r) {{ return r.text(); }}).then(function (html) {{
        document.getElementById('reports').innerHTML = html; }});
    }} else if (job.state === 'failed') {{
      show(job.message, '', true); busy(false);
    }} else {{
      show(job.message, job.detail); setTimeout(function () {{ poll(id); }}, 800);
    }}
  }});
}}
</script>
</body>
</html>
"""


def make_handler(reports_dir: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the terminal quiet
            pass

        def send(self, code: int, body: str | bytes, content_type: str = "text/html; charset=utf-8") -> None:
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def send_json(self, code: int, payload: dict) -> None:
            self.send(code, json.dumps(payload), "application/json; charset=utf-8")

        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            if path == "/":
                return self.send(200, render_home(reports_dir))
            if path == "/reports-table":
                html = render_home(reports_dir)
                start = html.index('<div id="reports">') + len('<div id="reports">')
                return self.send(200, html[start:html.index("</div>", start)])
            if path.startswith("/status/"):
                job = JOBS.get(path.rsplit("/", 1)[-1])
                return self.send_json(200 if job else 404, job or {"state": "failed", "message": "Unknown scan."})
            if path.startswith("/reports/"):
                name = path[len("/reports/"):]
                target = (reports_dir / name).resolve()
                if ("/" in name or "\\" in name or target.parent != reports_dir.resolve()
                        or target.suffix not in SERVED_SUFFIXES or not target.exists()):
                    return self.send(404, "Not found")
                return self.send(200, target.read_bytes(), SERVED_SUFFIXES[target.suffix])
            return self.send(404, "Not found")

        def do_POST(self):
            route = urlsplit(self.path).path
            if route not in ("/scan", "/scan-files"):
                return self.send(404, "Not found")
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > MAX_UPLOAD_BYTES:
                    return self.send_json(413, {"error": "Too much data. Scan fewer pages at a time."})
                data = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self.send_json(400, {"error": "The request was not valid."})
            brands = [str(b) for b in data.get("brands") or [] if str(b).strip()]
            url, max_pages, saved = "", DEFAULT_MAX_PAGES, None
            if route == "/scan":
                url = str(data.get("url", "")).strip()
                if urlsplit(url).scheme not in ("http", "https") or not urlsplit(url).netloc:
                    return self.send_json(400, {"error": "Enter a full address that starts with http:// or https://"})
                max_pages = max(1, min(int(data.get("max_pages") or DEFAULT_MAX_PAGES), 200))
            else:
                saved = [
                    (str(f.get("name", "page.html")), str(f.get("content", "")))
                    for f in data.get("files") or []
                    if str(f.get("name", "")).lower().endswith((".html", ".htm"))
                    and "_files/" not in str(f.get("name", "")).replace("\\", "/")
                ]
                if not saved:
                    return self.send_json(400, {"error": "Choose at least one saved .html page."})
            with JOB_LOCK:
                if any(j["state"] in ("queued", "running") for j in JOBS.values()):
                    return self.send_json(409, {"error": "A scan is already running. Wait for it to finish."})
                job_id = uuid.uuid4().hex[:12]
                JOBS[job_id] = {"id": job_id, "state": "queued", "message": "Queued", "detail": ""}
            threading.Thread(target=run_job, args=(job_id, url, brands, max_pages, reports_dir, saved),
                             daemon=True).start()
            return self.send_json(202, {"id": job_id})

    return Handler


def serve(port: int = PORT, reports_dir: Path = Path("reports"), open_browser: bool = True) -> None:
    server = ThreadingHTTPServer((HOST, port), make_handler(reports_dir))
    url = f"http://{HOST}:{port}/"
    print(f"Quebec French Scanner is running at {url}")
    print("Leave this window open while you use it. Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
