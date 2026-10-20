"""Score a scan report against the fixture ground truth (expected.json).

Rules agreed on 2026-10-19:
  * A string repeated on many pages counts as one finding.
  * "Needs review" is scored on its own. Precision and recall cover clear
    findings only.

Definitions:
  precision   = report findings that match a "flag" case / all report findings
  recall      = "flag" cases found as findings / all "flag" cases
  review hit  = "needs_review" cases reported as needs review / all of them
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

CATEGORY_TYPES = {
    "missing_french_page": {"missing_french_page"},
    "leftover_english": {"leftover_english", "possible_quoted_title", "tolerated_anglicism"},
    "metadata": {
        "wrong_lang_attribute", "missing_lang_attribute", "missing_title",
        "leftover_english_title", "missing_meta_description", "leftover_english_metadata",
    },
    "terminology": {"terminology", "terminology_review", "france_french_term"},
}


def path_of(url: str) -> str:
    return urlsplit(url).path or "/"


def page_matches(case: dict, item: dict) -> bool:
    paths = {path_of(u) for u in item["pages"]}
    if case["page"] == "*fr":
        return any(p.startswith("/fr/") for p in paths)
    return case["page"] in paths


def text_matches(case_text: str, item_text: str) -> bool:
    a, b = case_text.casefold(), item_text.casefold()
    pattern = r"(?<!\w){}(?!\w)"
    return bool(re.search(pattern.format(re.escape(a)), b) or re.search(pattern.format(re.escape(b)), a))


def matches(case: dict, item: dict) -> bool:
    if item["type"] not in CATEGORY_TYPES[case["category"]]:
        return False
    if case.get("finding") and case["expected"] == "flag" and item["severity"] == "finding":
        if item["type"] != case["finding"]:
            return False
    if not page_matches(case, item):
        return False
    case_text = case.get("text")
    if case_text and item.get("text") and case["element"] != "html@lang":
        return text_matches(case_text, item["text"])
    return True


def score(report: dict, expected: dict, categories: set[str] | None = None) -> dict:
    cases = [c for c in expected["cases"] if not categories or c["category"] in categories]
    items = report["findings"] + report["needs_review"]
    matched_items: set[int] = set()
    per_case = []

    flag_cases_all = [c for c in cases if c["expected"] == "flag"]

    def explained_by_flag(item: dict) -> bool:
        return any(matches(c, item) for c in flag_cases_all)

    for case in cases:
        hits = [i for i, item in enumerate(items) if matches(case, item)]
        if case["expected"] != "flag":
            # An item that is a correct finding for another case does not
            # count against this one. Example: the English footer contains
            # the brand name, but it is the LE-05 finding, not an LE-06 error.
            hits = [i for i in hits if not explained_by_flag(items[i])]
        as_finding = [i for i in hits if items[i]["severity"] == "finding"]
        as_review = [i for i in hits if items[i]["severity"] == "needs_review"]
        matched_items.update(hits)
        expected_result = case["expected"]
        if expected_result == "flag":
            outcome = "found" if as_finding else ("sent_to_review" if as_review else "missed")
        elif expected_result == "no_finding":
            outcome = "false_positive" if as_finding else ("sent_to_review" if as_review else "correct")
        else:  # needs_review
            outcome = "correct" if as_review else ("flagged_as_finding" if as_finding else "missed")
        per_case.append({"id": case["id"], "category": case["category"], "expected": expected_result,
                         "outcome": outcome, "matched": [items[i]["text"] or items[i]["type"] for i in hits]})

    flag_ids = {c["id"] for c in cases if c["expected"] == "flag"}
    report_findings = [i for i, item in enumerate(items) if item["severity"] == "finding"]
    good_findings = {
        i for i in report_findings
        if any(c["id"] in flag_ids and matches(c, items[i]) for c in cases)
    }
    unexpected = [
        {"type": items[i]["type"], "text": items[i]["text"], "pages": [path_of(u) for u in items[i]["pages"]]}
        for i in range(len(items)) if i not in matched_items
        and (not categories or any(items[i]["type"] in CATEGORY_TYPES[c] for c in categories))
    ]

    flag_cases = [c for c in per_case if c["expected"] == "flag"]
    review_cases = [c for c in per_case if c["expected"] == "needs_review"]
    scoped_findings = [
        i for i in report_findings
        if not categories or any(items[i]["type"] in CATEGORY_TYPES[c] for c in categories)
    ]

    def ratio(a: int, b: int) -> float | None:
        return round(a / b, 3) if b else None

    by_category = {}
    for cat in sorted({c["category"] for c in per_case}):
        rows = [c for c in per_case if c["category"] == cat]
        flags = [c for c in rows if c["expected"] == "flag"]
        by_category[cat] = {
            "flag_cases": len(flags),
            "found": sum(1 for c in flags if c["outcome"] == "found"),
            "false_positives": sum(1 for c in rows if c["outcome"] == "false_positive"),
            "review_cases": sum(1 for c in rows if c["expected"] == "needs_review"),
            "review_correct": sum(1 for c in rows if c["expected"] == "needs_review" and c["outcome"] == "correct"),
        }

    return {
        "precision": ratio(len(good_findings & set(scoped_findings)), len(scoped_findings)),
        "recall": ratio(sum(1 for c in flag_cases if c["outcome"] == "found"), len(flag_cases)),
        "false_positive_rate": ratio(len(set(scoped_findings) - good_findings), len(scoped_findings)),
        "review_hit_rate": ratio(sum(1 for c in review_cases if c["outcome"] == "correct"), len(review_cases)),
        "report_findings": len(scoped_findings),
        "report_needs_review": sum(1 for i, it in enumerate(items) if it["severity"] == "needs_review"
                                   and (not categories or any(it["type"] in CATEGORY_TYPES[c] for c in categories))),
        "by_category": by_category,
        "cases": per_case,
        "unexpected": unexpected,
    }


def load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def format_score(result: dict) -> str:
    def pct(x):
        return "n/a" if x is None else f"{x:.0%}"

    lines = [
        f"Precision           {pct(result['precision'])}",
        f"Recall              {pct(result['recall'])}",
        f"False positive rate {pct(result['false_positive_rate'])}",
        f"Needs review hits   {pct(result['review_hit_rate'])}",
        f"Report: {result['report_findings']} findings, {result['report_needs_review']} needs review",
        "",
        f"{'Category':22}{'Found':>8}{'FP':>5}{'Review':>9}",
    ]
    for cat, row in result["by_category"].items():
        lines.append(f"{cat:22}{row['found']:>4}/{row['flag_cases']:<3}{row['false_positives']:>5}"
                     f"{row['review_correct']:>6}/{row['review_cases']}")
    problems = [c for c in result["cases"] if c["outcome"] not in ("found", "correct")]
    if problems:
        lines += ["", "Cases not passed:"]
        lines += [f"  {c['id']:6} expected {c['expected']:12} got {c['outcome']}" for c in problems]
    if result["unexpected"]:
        lines += ["", "Report items that match no case:"]
        lines += [f"  {u['type']}: {u['text']!r} on {', '.join(u['pages'][:3])}" for u in result["unexpected"]]
    return "\n".join(lines)
