"""Crawler and pairing tests against the fixture site."""

from __future__ import annotations

import pytest

from qfscan.crawl import crawl, language_from_url, normalize_url


@pytest.fixture(scope="module")
def result(fixture_url):
    return crawl(fixture_url, delay=0)


def path(url: str) -> str:
    return "/" + url.split("/", 3)[3]


def test_finds_every_page(result):
    paths = {path(u) for u in result.pages}
    assert len(paths) == 20
    assert "/en/careers/" in paths
    assert "/fr/blogue/lancement/" in paths
    assert not result.hit_page_cap


def test_language_ignores_wrong_lang_attribute(result):
    terms = next(p for u, p in result.pages.items() if path(u) == "/fr/conditions/")
    assert terms.html_lang == "en"
    assert terms.language == "fr"
    assert terms.language_source == "hreflang"


def test_pairs(result):
    pairs = {path(p.en): (p.fr and path(p.fr), p.method) for p in result.pairs}
    assert len(pairs) == 10
    assert pairs["/en/about/"] == ("/fr/a-propos/", "hreflang")  # MP-02
    assert pairs["/en/blog/launch/"] == ("/fr/blogue/lancement/", "switcher")  # MP-03
    assert pairs["/en/careers/"] == (None, "none")  # MP-01
    assert sum(1 for fr, _ in pairs.values() if fr) == 9


def test_page_cap(fixture_url):
    small = crawl(fixture_url, max_pages=5, delay=0)
    assert len(small.pages) == 5
    assert small.hit_page_cap


@pytest.mark.parametrize(
    "url, lang",
    [
        ("https://example.com/fr/produits/", "fr"),
        ("https://example.com/fr-ca/", "fr"),
        ("https://example.com/en", "en"),
        ("https://fr.example.com/a", "fr"),
        ("https://example.com/shop?lang=fr", "fr"),
        ("https://example.com/french-press/", None),
        ("https://example.com/products/", None),
    ],
)
def test_language_from_url(url, lang):
    assert language_from_url(url) == lang


def test_normalize_url():
    assert normalize_url("HTTP://Example.com#top") == "http://example.com/"
    assert normalize_url("https://example.com/a?b=1#c") == "https://example.com/a?b=1"
