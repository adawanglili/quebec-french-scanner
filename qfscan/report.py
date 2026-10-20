"""Build the JSON scan report."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from . import __version__
from .checks import FINDING, NEEDS_REVIEW, Finding
from .crawl import CrawlResult

DISCLAIMER = (
    "This report lists potential French language gaps for human review. "
    "It is not legal advice and does not say whether the site complies with the law."
)


def build_report(result: CrawlResult, findings: list[Finding]) -> dict:
    ordered = sorted(findings, key=lambda f: (f.severity != FINDING, f.type, f.pages[0], f.text or ""))
    findings_only = [f for f in ordered if f.severity == FINDING]
    review_only = [f for f in ordered if f.severity == NEEDS_REVIEW]
    fr_pages = [p for p in result.pages.values() if p.language == "fr" and p.status == 200]
    en_pages = [p for p in result.pages.values() if p.language == "en" and p.status == 200]
    return {
        "tool": f"qfscan {__version__}",
        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "start_url": result.start_url,
        "disclaimer": DISCLAIMER,
        "summary": {
            "pages_crawled": len(result.pages),
            "french_pages": len(fr_pages),
            "english_pages": len(en_pages),
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
