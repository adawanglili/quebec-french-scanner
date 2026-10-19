"""Command line entry point.

Examples:
    python -m qfscan scan http://localhost:8000/ --out reports/fixture.json
    python -m qfscan score reports/fixture.json
    python -m qfscan scan https://example.com/ --brand "Example Inc" --max-pages 30
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .checks import run_checks
from .crawl import DEFAULT_MAX_PAGES, crawl
from .report import build_report
from .score import format_score, load, score

EXPECTED = Path(__file__).resolve().parent.parent / "fixtures" / "expected.json"


def cmd_scan(args) -> int:
    print(f"Crawling {args.url} (up to {args.max_pages} pages)...", file=sys.stderr)
    result = crawl(args.url, max_pages=args.max_pages, delay=args.delay, respect_robots=not args.ignore_robots)
    findings = run_checks(result, brands=args.brand)
    report = build_report(result, findings)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"Report written to {args.out}", file=sys.stderr)
    else:
        print(text)
    s = report["summary"]
    print(
        f"{s['pages_crawled']} pages, {s['pairs']} pairs, {s['findings']} findings, "
        f"{s['needs_review']} needs review", file=sys.stderr,
    )
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
    scan.add_argument("--out", help="Write the JSON report to this file")
    scan.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    scan.add_argument("--delay", type=float, default=0.5, help="Seconds between requests")
    scan.add_argument("--brand", action="append", help="Brand or product name to ignore. Repeat for several.")
    scan.add_argument("--ignore-robots", action="store_true", help="Only for your own site")
    scan.set_defaults(func=cmd_scan)

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
