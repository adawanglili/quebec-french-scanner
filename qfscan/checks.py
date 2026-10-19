"""Run the checks on a crawl and return deduplicated findings.

Checks in this module:
  * missing French page (from the crawl pairing)
  * leftover English in visible text and attributes of French pages
  * metadata of French pages: lang attribute, title, meta description

A string repeated on many pages, like a shared menu item, is one finding with
a list of pages.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from .crawl import CrawlResult, Page, primary_language
from .rules import RULES
from .text import brand_words_from, extract_units, judge_language

FINDING = "finding"
NEEDS_REVIEW = "needs_review"
TITLE_SEPARATORS = re.compile(r"\s+[|\-–—·:]\s+")


@dataclass
class Finding:
    type: str
    severity: str  # FINDING or NEEDS_REVIEW
    text: str | None
    element: str
    pages: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)

    @property
    def key(self) -> tuple:
        # Page level findings are unique per page. Text findings dedupe by text.
        if self.text is None:
            return (self.type, self.pages[0])
        return (self.type, self.text.casefold())

    def to_dict(self) -> dict:
        rule = RULES.get(self.type, {})
        return {
            "type": self.type,
            "severity": self.severity,
            "text": self.text,
            "element": self.element,
            "pages": self.pages,
            "occurrences": len(self.pages),
            "why": rule.get("why"),
            "reference": rule.get("reference"),
            "fix": rule.get("fix"),
            "evidence": self.evidence,
        }


def detect_brand(result: CrawlResult, extra: list[str] | None = None) -> set[str]:
    """Brand words from the home link text and repeated title parts."""
    texts = list(extra or [])
    pages = [p for p in result.pages.values() if p.status == 200]
    for page in pages:
        soup = BeautifulSoup(page.html, "html.parser")
        scope = soup.find("header") or soup
        for a in scope.find_all("a", href=True):
            classes = " ".join(a.get("class") or [])
            if "logo" in classes or "brand" in classes:
                texts.append(a.get_text(" ", strip=True))
                break
    parts = Counter()
    for page in pages:
        if page.title:
            for part in set(TITLE_SEPARATORS.split(page.title)):
                parts[part.strip()] += 1
    texts += [part for part, n in parts.items() if part and n >= max(2, len(pages) // 2)]
    return brand_words_from([t for t in texts if t])


def check_missing_french(result: CrawlResult) -> list[Finding]:
    return [
        Finding("missing_french_page", FINDING, None, "page", [pair.en])
        for pair in result.pairs
        if pair.fr is None
    ]


def check_leftover_english(page: Page, brand: set[str]) -> list[Finding]:
    findings = []
    for unit in extract_units(page.html):
        verdict = judge_language(unit.text, brand)
        if not verdict or not verdict.is_english:
            continue
        evidence = {
            "english_confidence": verdict.english_confidence,
            "english_words": verdict.english_words,
            "french_words": verdict.french_words,
        }
        if unit.tag in {"em", "i", "cite", "q"} and unit.kind == "text":
            findings.append(Finding("possible_quoted_title", NEEDS_REVIEW, unit.text, unit.element, [page.url], evidence))
        else:
            findings.append(Finding("leftover_english", FINDING, unit.text, unit.element, [page.url], evidence))
    return findings


def check_metadata(page: Page, brand: set[str]) -> list[Finding]:
    findings = []
    lang = primary_language(page.html_lang)
    if not page.html_lang:
        findings.append(Finding("missing_lang_attribute", FINDING, None, "html@lang", [page.url]))
    elif lang != "fr":
        findings.append(Finding("wrong_lang_attribute", FINDING, None, "html@lang", [page.url],
                                {"lang": page.html_lang}))

    if not page.title:
        findings.append(Finding("missing_title", FINDING, None, "title", [page.url]))
    else:
        verdict = judge_language(page.title, brand)
        if verdict and verdict.is_english:
            findings.append(Finding("leftover_english_title", FINDING, page.title, "title", [page.url],
                                    {"english_confidence": verdict.english_confidence}))

    if not page.description:
        findings.append(Finding("missing_meta_description", FINDING, None, "meta[name=description]", [page.url]))
    else:
        verdict = judge_language(page.description, brand)
        if verdict and verdict.is_english:
            findings.append(Finding("leftover_english_metadata", FINDING, page.description,
                                    "meta[name=description]", [page.url],
                                    {"english_confidence": verdict.english_confidence}))
    return findings


def merge(findings: list[Finding]) -> list[Finding]:
    """Merge findings with the same key and collect their pages."""
    merged: dict[tuple, Finding] = {}
    for f in findings:
        if f.key in merged:
            kept = merged[f.key]
            kept.pages.extend(p for p in f.pages if p not in kept.pages)
        else:
            merged[f.key] = f
    return list(merged.values())


def run_checks(result: CrawlResult, brands: list[str] | None = None) -> list[Finding]:
    brand = detect_brand(result, brands)
    findings = check_missing_french(result)
    for page in result.pages.values():
        if page.status != 200 or page.language != "fr":
            continue
        findings += check_metadata(page, brand)
        findings += check_leftover_english(page, brand)
    return merge(findings)
