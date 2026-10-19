"""Turn a JSON scan report into a readable HTML page and a review sheet.

The HTML page is one self contained file with no outside links except the
GDT records. Open it in any browser.

The review sheet is a CSV file that opens in Excel. It has one row per
finding and empty columns for your verdict, so you can measure precision on a
real site.
"""

from __future__ import annotations

import csv
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

TYPE_LABELS = {
    "missing_french_page": "Missing French page",
    "leftover_english": "English text on a French page",
    "leftover_english_title": "English page title",
    "leftover_english_metadata": "English meta description",
    "missing_meta_description": "Missing meta description",
    "missing_title": "Missing page title",
    "wrong_lang_attribute": "Wrong language tag",
    "missing_lang_attribute": "Missing language tag",
    "terminology": "Quebec French term",
    "tolerated_anglicism": "Tolerated borrowing",
    "terminology_review": "Term to check in context",
    "possible_quoted_title": "Possible title of a work",
}

CSS = """
:root { --bg:#fbfaf7; --card:#fff; --ink:#1f1d1a; --muted:#6b665e; --line:#e6e1d8;
  --accent:#1f5f8b; --warn:#a4501a; --review:#6a4fa3; --chip:#f1ede6; }
@media (prefers-color-scheme: dark) { :root { --bg:#171615; --card:#211f1d; --ink:#ece8e1;
  --muted:#a59f95; --line:#38342f; --accent:#7cb4dc; --warn:#e39a62; --review:#b39ce6; --chip:#2c2926; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
.wrap { max-width:960px; margin:0 auto; padding:32px 16px 64px; }
h1 { font-size:1.6rem; margin:0 0 4px; }
h2 { font-size:1.15rem; margin:36px 0 12px; padding-bottom:6px; border-bottom:1px solid var(--line); }
.meta, .muted { color:var(--muted); font-size:.9rem; }
.note { background:var(--chip); border-radius:8px; padding:10px 14px; font-size:.9rem; margin:16px 0; }
.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px; margin:20px 0; }
.stat { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 14px; }
.stat b { display:block; font-size:1.6rem; line-height:1.2; }
.stat span { color:var(--muted); font-size:.85rem; }
.group h3 { font-size:1rem; margin:24px 0 8px; }
.group h3 .count { color:var(--muted); font-weight:normal; }
.item { background:var(--card); border:1px solid var(--line); border-left:4px solid var(--warn);
  border-radius:8px; padding:12px 14px; margin:8px 0; }
.item.review { border-left-color:var(--review); }
.item .text { font-family:ui-monospace, Consolas, monospace; font-size:.95rem; word-break:break-word; }
.item .row { margin-top:6px; font-size:.9rem; }
.item .row b { color:var(--muted); font-weight:600; margin-right:4px; }
.chip { display:inline-block; background:var(--chip); border-radius:999px; padding:1px 8px;
  font-size:.8rem; margin-right:6px; color:var(--muted); }
a { color:var(--accent); }
details { margin-top:6px; font-size:.88rem; }
summary { cursor:pointer; color:var(--muted); }
details ul { margin:6px 0 0; padding-left:20px; }
table { border-collapse:collapse; width:100%; font-size:.88rem; }
th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); vertical-align:top; }
th { color:var(--muted); font-weight:600; }
"""


def label(kind: str) -> str:
    return TYPE_LABELS.get(kind, kind.replace("_", " ").capitalize())


def short(url: str) -> str:
    parts = urlsplit(url)
    return (parts.path or "/") + (f"?{parts.query}" if parts.query else "")


def render_item(item: dict, review: bool) -> str:
    ev = item.get("evidence") or {}
    text = item.get("text")
    rows = []
    if text:
        rows.append(f'<div class="text">{escape(text)}</div>')
    else:
        rows.append(f'<div class="text">{escape(short(item["pages"][0]))}</div>')
    chips = [f'<span class="chip">{escape(item["element"])}</span>']
    if item["occurrences"] > 1:
        chips.append(f'<span class="chip">{item["occurrences"]} pages</span>')
    if "english_confidence" in ev:
        chips.append(f'<span class="chip">English {ev["english_confidence"]:.0%}</span>')
    rows.append(f'<div class="row">{"".join(chips)}</div>')
    if ev.get("suggestion"):
        rows.append(f'<div class="row"><b>Suggestion</b>{escape(ev["suggestion"])}</div>')
    if ev.get("context"):
        rows.append(f'<div class="row"><b>Context</b>… {escape(ev["context"])} …</div>')
    rows.append(f'<div class="row"><b>Why</b>{escape(item["why"] or "")}</div>')
    rows.append(f'<div class="row"><b>Fix</b>{escape(item["fix"] or "")}</div>')
    reference = escape(item["reference"] or "")
    if ev.get("gdt_record"):
        reference += f' <a href="{escape(ev["gdt_record"])}" target="_blank" rel="noopener">Open the GDT record</a>'
    rows.append(f'<div class="row"><b>Reference</b>{reference}</div>')
    if ev.get("note"):
        rows.append(f'<div class="row"><b>Note</b>{escape(ev["note"])}</div>')
    links = "".join(
        f'<li><a href="{escape(u)}" target="_blank" rel="noopener">{escape(short(u))}</a></li>'
        for u in item["pages"]
    )
    page_word = "page" if len(item["pages"]) == 1 else "pages"
    rows.append(f'<details><summary>Show {len(item["pages"])} {page_word}</summary><ul>{links}</ul></details>')
    return f'<div class="item{" review" if review else ""}">{"".join(rows)}</div>'


def render_group(items: list[dict], review: bool) -> str:
    groups: dict[str, list[dict]] = {}
    for item in items:
        groups.setdefault(item["type"], []).append(item)
    out = []
    for kind, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        body = "".join(render_item(m, review) for m in members)
        out.append(f'<div class="group"><h3>{escape(label(kind))} <span class="count">({len(members)})</span></h3>{body}</div>')
    return "".join(out) or '<p class="muted">None.</p>'


def render_html(report: dict) -> str:
    s = report["summary"]
    crawl = report.get("crawl", {})
    host = urlsplit(report["start_url"]).netloc
    stats = [
        (s["findings"], "findings"),
        (s["needs_review"], "need review"),
        (s["french_pages"], "French pages checked"),
        (s["pairs"], "English and French pairs"),
        (s["english_pages_without_french"], "English pages with no French"),
    ]
    stat_html = "".join(f'<div class="stat"><b>{n}</b><span>{escape(t)}</span></div>' for n, t in stats)
    cap = (
        '<div class="note">The scan stopped at the page limit. Pages beyond the limit were not checked.</div>'
        if s.get("hit_page_cap") else ""
    )
    pairs = "".join(
        f'<tr><td>{escape(short(p["en"]))}</td><td>{escape(short(p["fr"])) if p["fr"] else "<b>none</b>"}</td>'
        f'<td>{escape(p["method"])}</td></tr>'
        for p in crawl.get("pairs", [])
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>French scan: {escape(host)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<h1>French language scan: {escape(host)}</h1>
<div class="meta">Started at {escape(report["start_url"])} · {escape(report["scanned_at"])} · {escape(report["tool"])} · {s["pages_crawled"]} pages crawled</div>
<div class="note">{escape(report["disclaimer"])}</div>
<div class="stats">{stat_html}</div>
{cap}
<h2>Findings</h2>
{render_group(report["findings"], review=False)}
<h2>Needs review</h2>
<p class="muted">Judgment calls. A person should decide.</p>
{render_group(report["needs_review"], review=True)}
<h2>Page pairs</h2>
<table><thead><tr><th>English page</th><th>French page</th><th>Matched by</th></tr></thead><tbody>{pairs}</tbody></table>
</div>
</body>
</html>
"""


SHEET_COLUMNS = [
    "id", "severity", "type", "text", "element", "occurrences", "first_page",
    "suggestion", "english_confidence", "verdict", "notes",
]


def write_sheet(report: dict, path: Path) -> int:
    """Write a review sheet. Fill in verdict with correct, wrong or unsure."""
    rows = []
    for n, item in enumerate(report["findings"] + report["needs_review"], start=1):
        ev = item.get("evidence") or {}
        rows.append({
            "id": n,
            "severity": item["severity"],
            "type": label(item["type"]),
            "text": item.get("text") or "",
            "element": item["element"],
            "occurrences": item["occurrences"],
            "first_page": item["pages"][0],
            "suggestion": ev.get("suggestion") or "",
            "english_confidence": ev.get("english_confidence", ""),
            "verdict": "",
            "notes": "",
        })
    # utf-8-sig so Excel shows accents correctly.
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
