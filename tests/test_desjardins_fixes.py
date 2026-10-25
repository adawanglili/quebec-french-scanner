"""Fixes found on the Desjardins scan (2026-10-22)."""

from qfscan.crawl import Page, duplicate_of, normalize_url
from qfscan.html import render_html
from qfscan.text import judge_language


def test_number_with_short_unit_is_not_judged():
    assert judge_language("1 an") is None
    assert judge_language("2 h") is None


def test_other_short_word_with_a_number_goes_to_review():
    for text in ("1 day", "5 pm", "2 hrs"):
        verdict = judge_language(text)
        assert verdict is not None and verdict.uncertain, text


def test_short_word_with_number_has_a_rule():
    from qfscan.rules import RULES
    assert RULES["short_word_with_number"]["why"]


def test_longer_unit_after_a_number_is_judged_normally():
    verdict = judge_language("3 mois")
    assert verdict is not None and not verdict.is_english


def test_short_english_text_is_still_english():
    verdict = judge_language("Close")
    assert verdict is not None and verdict.is_english


def test_tracking_parameters_are_dropped():
    assert normalize_url("https://x.ca/fr/taux.html?utm_source=a&id=3") == "https://x.ca/fr/taux.html?id=3"
    assert normalize_url("https://x.ca/fr/?gclid=abc") == "https://x.ca/fr/"


def test_page_with_a_query_is_a_duplicate_of_its_hreflang_page():
    crawled = {"https://x.ca/fr/taux.html": Page("https://x.ca/fr/taux.html", 200)}
    page = Page("https://x.ca/fr/taux.html?navigMW=pp", 200, language="fr",
                alternates={"fr-ca": "https://x.ca/fr/taux.html", "en-ca": "https://x.ca/en/rates.html"})
    assert duplicate_of(page, crawled) == "https://x.ca/fr/taux.html"


def test_page_with_a_canonical_link_is_a_duplicate():
    crawled = {"https://x.ca/fr/": Page("https://x.ca/fr/", 200)}
    page = Page("https://x.ca/fr/?promo=1", 200, language="fr", canonical="https://x.ca/fr/")
    assert duplicate_of(page, crawled) == "https://x.ca/fr/"


def test_new_page_is_not_a_duplicate():
    page = Page("https://x.ca/fr/a.html", 200, language="fr",
                alternates={"fr-ca": "https://x.ca/fr/a.html"}, canonical="https://x.ca/fr/a.html")
    assert duplicate_of(page, {}) is None


def summary(**extra):
    base = {"pages_crawled": 50, "french_pages": 50, "english_pages": 0, "pairs": 0,
            "french_pages_linked_not_crawled": 0, "start_redirect": None,
            "english_pages_without_french": 0, "hit_page_cap": True,
            "findings": 0, "needs_review": 0, "findings_by_type": {}}
    base.update(extra)
    return {"tool": "qfscan", "scanned_at": "2026-10-22", "start_url": "https://x.ca/fr",
            "disclaimer": "", "summary": base, "findings": [], "needs_review": [],
            "crawl": {"pages": [], "pairs": [], "skipped": []}}


def test_report_does_not_call_a_bilingual_site_french_only():
    html = render_html(summary(english_versions_linked_not_crawled=40))
    assert "French only" not in html
    assert "link to 40 English versions" in html


def test_report_still_says_french_only_when_no_english_is_linked():
    html = render_html(summary(english_versions_linked_not_crawled=0))
    assert "French only" in html
