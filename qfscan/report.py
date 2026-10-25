"""Build the JSON scan report."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from . import __version__
from .checks import FINDING, NEEDS_REVIEW, Finding
from .crawl import CrawlResult

DISCLAIMER = (
    "This report lists French market fit opportunities for human review. "
    "It comes from an experimental personal project. It is not legal advice and "
    "does not assess compliance with any law. Findings are language suggestions "
    "based on public OQLF and Quebec government resources."
)


def build_report(result: CrawlResult, findings: list[Finding]) -> dict:
    ordered = sorted(findings, key=lambda f: (f.severity != FINDING, f.type, f.pages[0], f.text or ""))
    findings_only = [f for f in ordered if f.severity == FINDING]
    review_only = [f for f in ordered if f.severity == NEEDS_REVIEW]
    fr_pages = [p for p in result.pages.values() if p.language == "fr" and p.status == 200]
    en_pages = [p for p in result.pages.values() if p.language == "en" and p.status == 200]
    english_linked = {
        href for p in fr_pages for code, href in p.alternates.items()
        if code.lower().split("-")[0] == "en" and href not in result.pages
    }
    return {
        "tool": f"qfscan {__version__}",
        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "start_url": result.start_url,
        "disclaimer": DISCLAIMER,
        "summary": {
            "pages_crawled": len(result.pages),
            "french_pages": len(fr_pages),
            "english_pages": len(en_pages),
            "english_versions_linked_not_crawled": len(english_linked),
            "pairs": sum(1 for p in result.pairs if p.fr and p.method != "not_crawled"),
            "french_pages_linked_not_crawled": sum(1 for p in result.pairs if p.method == "not_crawled"),
            "start_redirect": result.start_redirect,
            "english_pages_without_french": sum(1 for p in result.pairs if not p.fr),
            "hit_page_cap": result.hit_page_cap,
            "findings": len(findings_only),
            "needs_review": len(review_only),
            "findings_by_type": dict(Counter(f.type for f in findings_only)),
        },
        "findings": [f.to_dict() for f in findings_only],
        "needs_review": [f.to_dict() for f in review_only],
        "crawl": result.to_dict(),
    }
