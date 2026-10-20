"""Command line entry point.

Examples:
    python -m qfscan scan https://example.com/
    python -m qfscan scan http://localhost:8000/ --out reports/fixture.json
    python -m qfscan score reports/fixture.json
    python -m qfscan view reports/fixture.json
    python -m qfscan serve
    python -m qfscan scan https://example.com/ --brand "Example Inc" --max-pages 30
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from .checks import run_checks
from .crawl import DEFAULT_MAX_PAGES, crawl
from .html import render_html, write_sheet
from .report import build_report
from .score import format_score, load, score

EXPECTED = Path(__file__).resolve().parent.parent / "fixtures" / "expected.json"


STATUS_HELP = {
    401: "The site asks for a login.",
    403: "The site refused the request. It probably blocks automated tools. "
         "The scanner does not try to get around this. Try another site, "
         "or ask the site owner to allow the qfscan user agent.",
    404: "The page was not found. Check the address.",
    429: "The site says there were too many requests. Wait and try again with a longer --delay.",
    503: "The site is unavailable or is showing a bot check page. Try again later or try another site.",
}


def scan_failure_message(result) -> str:
    if not result.pages:
        reasons = "; ".join(f"{s['url']}: {s['reason']}" for s in result.skipped[:3]) or "no response"
        return f"Scan failed. No page could be fetched ({reasons})."
    first = next(iter(result.pages.values()))
    help_text = STATUS_HELP.get(first.status, "The site did not return a normal page.")
    return f"Scan failed. {first.url} returned HTTP {first.status}. {help_text}"


REPORTS_DIR = Path("reports")


def default_report_name(url: str, now: datetime | None = None) -> str:
    """'https://www.canada.ca/fr.html' -> 'canada.ca_2026-10-19_1644.json'"""
    host = urlsplit(url if "//" in url else "//" + url).netloc.lower().removeprefix("www.")
    host = re.sub(r"[^a-z0-9.-]", "-", host) or "site"
    stamp = (now or datetime.now()).strftime("%Y-%m-%d_%H%M")
    return f"{host}_{stamp}.json"


def report_path(url: str, out: str | None, overwrite: bool = False) -> Path:
    """Pick the report file. Never replace an existing report unless asked."""
    path = Path(out) if out else REPORTS_DIR / default_report_name(url)
    if path.suffix.lower() != ".json":
        path = path.with_suffix(".json")
    if overwrite or not path.exists():
        return path
    n = 2
    while (candidate := path.with_name(f"{path.stem}_{n}{path.suffix}")).exists():
        n += 1
    print(f"{path} already exists. Saving as {candidate.name} instead. "
          f"Use --overwrite to replace it.", file=sys.stderr)
    return candidate


def cmd_scan(args) -> int:
    print(f"Crawling {args.url} (up to {args.max_pages} pages)...", file=sys.stderr)
    result = crawl(args.url, max_pages=args.max_pages, delay=args.delay, respect_robots=not args.ignore_robots)
    ok_pages = [p for p in result.pages.values() if p.status == 200]
    if not ok_pages:
        print(scan_failure_message(result), file=sys.stderr)
        return 2
    failed = [p for p in result.pages.values() if p.status != 200]
    if failed:
        print(f"Warning: {len(failed)} pages returned an error status and were not checked.", file=sys.stderr)
    findings = run_checks(result, brands=args.brand)
    report = build_report(result, findings)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    out = report_path(args.url, args.out, args.overwrite)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(f"Report written to {out}", file=sys.stderr)
    write_views(out, report)
    s = report["summary"]
    print(
        f"{s['pages_crawled']} pages, {s['pairs']} pairs, {s['findings']} findings, "
        f"{s['needs_review']} needs review", file=sys.stderr,
    )
    return 0


def write_views(json_path: Path, report: dict) -> None:
    html_path = json_path.with_suffix(".html")
    sheet_path = json_path.with_name(json_path.stem + "-review.csv")
    html_path.write_text(render_html(report), encoding="utf-8")
    rows = write_sheet(report, sheet_path)
    print(f"Readable report: {html_path}", file=sys.stderr)
    print(f"Review sheet ({rows} rows): {sheet_path}", file=sys.stderr)


def cmd_view(args) -> int:
    write_views(Path(args.report), load(args.report))
    return 0


def cmd_serve(args) -> int:
    from .server import serve
    serve(port=args.port, open_browser=not args.no_browser)
    return 0


def cmd_score(args) -> int:
    result = score(load(args.report), load(args.expected), set(args.category) if args.category else None)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_score(result))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qfscan", description="Quebec French website scanner")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Crawl a site and report French language gaps")
    scan.add_argument("url")
    scan.add_argument("--out", help="Report file name. Default: reports/<site>_<date>_<time>.json")
    scan.add_argument("--overwrite", action="store_true", help="Replace the --out file if it exists")
    scan.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    scan.add_argument("--delay", type=float, default=0.5, help="Seconds between requests")
    scan.add_argument("--brand", action="append", help="Brand or product name to ignore. Repeat for several.")
    scan.add_argument("--ignore-robots", action="store_true", help="Only for your own site")
    scan.set_defaults(func=cmd_scan)

    view = sub.add_parser("view", help="Make a readable HTML report and a review sheet from a JSON report")
    view.add_argument("report")
    view.set_defaults(func=cmd_view)

    srv = sub.add_parser("serve", help="Open a local web page for running scans")
    srv.add_argument("--port", type=int, default=8765)
    srv.add_argument("--no-browser", action="store_true", help="Do not open the browser")
    srv.set_defaults(func=cmd_serve)

    sc = sub.add_parser("score", help="Score a report against the fixture ground truth")
    sc.add_argument("report")
    sc.add_argument("--expected", default=str(EXPECTED))
    sc.add_argument("--category", action="append", help="Limit to a category. Repeat for several.")
    sc.add_argument("--json", action="store_true")
    sc.set_defaults(func=cmd_score)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
