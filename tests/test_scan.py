"""End to end scan of the fixture, plus unit tests for the language decision."""

from __future__ import annotations

import pytest

from qfscan.checks import run_checks
from qfscan.crawl import crawl
from qfscan.report import build_report
from qfscan.score import load, score
from qfscan.terms import find_records_file
from qfscan.text import judge_language

EXPECTED = load("fixtures/expected.json")
HAS_DATA = find_records_file() is not None


@pytest.fixture(scope="module")
def report(fixture_url):
    result = crawl(fixture_url, delay=0)
    return build_report(result, run_checks(result))


@pytest.mark.skipif(not HAS_DATA, reason="OQLF data not downloaded")
def test_fixture_scores_perfectly(report):
    result = score(report, EXPECTED)
    failing = [c for c in result["cases"] if c["outcome"] not in ("found", "correct")]
    assert failing == []
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["review_hit_rate"] == 1.0
    assert result["unexpected"] == []


def test_checks_without_terminology_score_perfectly(report):
    result = score(report, EXPECTED, {"missing_french_page", "leftover_english", "metadata"})
    failing = [c for c in result["cases"] if c["outcome"] not in ("found", "correct")
               and not (c["id"] == "LE-07" and not HAS_DATA)]
    assert failing == []
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0


def test_shared_strings_count_once(report):
    contact = [f for f in report["findings"] if f["text"] == "Contact us"]
    assert len(contact) == 1
    assert contact[0]["occurrences"] == 9


def test_every_finding_explains_itself(report):
    for item in report["findings"] + report["needs_review"]:
        assert item["why"] and item["reference"] and item["fix"]


@pytest.mark.parametrize(
    "text, english",
    [
        ("Contact us", True),
        ("Add to cart", True),
        ("This field is required", True),
        ("Our coffees", True),
        ("Nous joindre", False),
        ("Panier", False),
        ("Message", False),
        ("Nom", False),
        ("Date d'expiration", False),
        ("Code de produit : SKU-4471", False),
        ("Blogue", False),
        ("Écrivez-nous par email à bonjour@northwind.example ou utilisez le formulaire ci-dessous.", False),
    ],
)
def test_judge_language(text, english):
    verdict = judge_language(text, {"northwind"})
    assert verdict is not None and verdict.is_english is english


def test_brand_only_text_is_skipped():
    assert judge_language("Northwind", {"northwind"}) is None


def test_image_file_names_are_not_text():
    from qfscan.text import extract_units
    units = extract_units('<body><img alt="teosyal puresense 1ml.jpg"><img alt="Femme qui sourit"></body>')
    assert [u.text for u in units] == ["Femme qui sourit"]
