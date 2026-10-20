"""Scanning pages saved from a browser."""

from __future__ import annotations

from pathlib import Path

from qfscan.files import find_html_files, load_saved_pages, original_url, path_url
from qfscan.score import load, score
from qfscan.checks import run_checks
from qfscan.report import build_report
from qfscan.terms import find_records_file

SITE = Path(__file__).resolve().parent.parent / "fixtures" / "site"


def test_fixture_from_files_matches_live_crawl():
    result = load_saved_pages([SITE])
    assert len(result.pages) == 20
    assert sum(1 for p in result.pairs if p.fr) == 9
    report = build_report(result, run_checks(result))
    scored = score(report, load("fixtures/expected.json"),
                   None if find_records_file() else {"missing_french_page", "leftover_english", "metadata"})
    assert scored["precision"] == 1.0 and scored["recall"] == 1.0


def test_chrome_style_save(tmp_path):
    fr = ('<!-- saved from url=(0035)https://northwind.example/fr/contact/ -->\n'
          '<html lang="fr-CA"><head><title>Nous joindre</title>'
          '<link rel="alternate" hreflang="en" href="https://northwind.example/en/contact/"></head>'
          '<body><button>Add to cart</button><p>Écrivez-nous.</p></body></html>')
    en = ('<html lang="en"><head><link rel="canonical" href="https://northwind.example/en/contact/">'
          '<link rel="alternate" hreflang="fr" href="https://northwind.example/fr/contact/"></head>'
          '<body><p>Write to us.</p></body></html>')
    (tmp_path / "Nous joindre _ Northwind.html").write_text(fr, encoding="utf-8")
    (tmp_path / "Contact us _ Northwind.html").write_text(en, encoding="utf-8")
    assets = tmp_path / "Nous joindre _ Northwind_files"
    assets.mkdir()
    (assets / "widget.html").write_text("<html><body>Ignore me</body></html>")

    assert len(find_html_files([tmp_path])) == 2
    result = load_saved_pages([tmp_path])
    assert set(result.pages) == {"https://northwind.example/fr/contact/", "https://northwind.example/en/contact/"}
    assert result.pairs[0].fr == "https://northwind.example/fr/contact/"
    texts = [f.text for f in run_checks(result)]
    assert "Add to cart" in texts


def test_address_fallbacks():
    assert path_url("fr/a-propos/index.html") == "https://saved-pages.local/fr/a-propos/"
    assert original_url('<meta property="og:url" content="https://x.ca/fr/">', "https://saved-pages.local/a") == "https://x.ca/fr/"
