"""Sanity checks for the fixture site.

These tests check the fixture itself, not the scanner. They make sure every
planted case is present where expected.json says it is, that planted words do
not leak onto other pages, and that every internal link works.

Run:
    python -m unittest discover tests
"""

from __future__ import annotations

import json
import re
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "fixtures" / "site"
EXPECTED = json.loads((ROOT / "fixtures" / "expected.json").read_text(encoding="utf-8"))
CASES = {c["id"]: c for c in EXPECTED["cases"]}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_lang = None
        self.title = ""
        self.description = None
        self.hreflang = {}
        self.links = []
        self.switcher = None
        self.text = []
        self.attrs_text = []
        self.comments = []
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.html_lang = a.get("lang")
        elif tag == "title":
            self._in_title = True
        elif tag == "meta" and a.get("name") == "description":
            self.description = a.get("content")
        elif tag == "link" and a.get("rel") == "alternate":
            self.hreflang[a.get("hreflang")] = a.get("href")
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
            if "lang-switch" in (a.get("class") or ""):
                self.switcher = a["href"]
        for key in ("alt", "placeholder", "content"):
            if a.get(key):
                self.attrs_text.append(a[key])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        else:
            self.text.append(data)

    def handle_comment(self, data):
        self.comments.append(data.strip())

    @property
    def all_text(self) -> str:
        return " ".join(self.text + self.attrs_text + [self.title, self.description or ""])


def url_to_file(path: str) -> Path:
    return SITE / path.strip("/") / "index.html" if path != "/" else SITE / "index.html"


def parse(path: str) -> PageParser:
    parser = PageParser()
    parser.feed(url_to_file(path).read_text(encoding="utf-8"))
    return parser


def all_pages() -> dict[str, PageParser]:
    pages = {}
    for f in SITE.rglob("index.html"):
        rel = f.parent.relative_to(SITE).as_posix()
        path = "/" if rel == "." else f"/{rel}/"
        pages[path] = parse(path)
    return pages


PAGES = all_pages()
FR_PAGES = {p: v for p, v in PAGES.items() if p.startswith("/fr/")}


def has_word(text: str, word: str) -> bool:
    return re.search(rf"(?<![\w@.-]){re.escape(word)}(?![\w-])", text, re.IGNORECASE) is not None


class TestCaseList(unittest.TestCase):
    def test_counts_match_coverage_table(self):
        self.assertEqual(len(CASES), 24)
        counts = Counter((c["category"], c["expected"]) for c in CASES.values())
        self.assertEqual(counts[("missing_french_page", "flag")], 1)
        self.assertEqual(counts[("missing_french_page", "no_finding")], 2)
        self.assertEqual(counts[("leftover_english", "flag")], 5)
        self.assertEqual(counts[("leftover_english", "no_finding")], 2)
        self.assertEqual(counts[("leftover_english", "needs_review")], 2)
        self.assertEqual(counts[("metadata", "flag")], 4)
        self.assertEqual(counts[("metadata", "no_finding")], 1)
        self.assertEqual(counts[("terminology", "flag")], 4)
        self.assertEqual(counts[("terminology", "no_finding")], 2)
        self.assertEqual(counts[("terminology", "needs_review")], 1)


class TestCasesArePlanted(unittest.TestCase):
    def test_each_case_page_exists_and_is_marked(self):
        for case in CASES.values():
            with self.subTest(case=case["id"]):
                if case["page"] == "*fr":
                    continue
                comments = PAGES[case["page"]].comments
                if case.get("pair"):
                    comments = comments + PAGES[case["pair"]].comments
                self.assertIn(f"case: {case['id']}", comments)

    def test_case_text_is_on_its_page(self):
        for case in CASES.values():
            text = case.get("text")
            if not text or case["element"] == "html@lang":
                continue
            targets = FR_PAGES.values() if case["page"] == "*fr" else [PAGES[case["page"]]]
            for page in targets:
                with self.subTest(case=case["id"]):
                    self.assertTrue(has_word(page.all_text, text), f"{text!r} missing")

    def test_missing_french_page(self):
        careers = PAGES["/en/careers/"]
        self.assertEqual(careers.hreflang, {})
        self.assertIsNone(careers.switcher)
        self.assertFalse(any(p.startswith("/fr/carri") for p in PAGES))
        for path, page in FR_PAGES.items():
            self.assertNotIn("/en/careers/", page.links, path)

    def test_hreflang_and_switcher_pairs(self):
        about_en, about_fr = PAGES["/en/about/"], PAGES["/fr/a-propos/"]
        self.assertEqual(about_en.hreflang.get("fr-CA"), "/fr/a-propos/")
        self.assertEqual(about_fr.hreflang.get("en-CA"), "/en/about/")
        blog_en, blog_fr = PAGES["/en/blog/launch/"], PAGES["/fr/blogue/lancement/"]
        self.assertEqual(blog_en.hreflang, {})
        self.assertEqual(blog_fr.hreflang, {})
        self.assertEqual(blog_en.switcher, "/fr/blogue/lancement/")
        self.assertEqual(blog_fr.switcher, "/en/blog/launch/")

    def test_metadata_is_clean_except_planted_pages(self):
        for path, page in FR_PAGES.items():
            with self.subTest(page=path):
                expected_lang = "en" if path == "/fr/conditions/" else "fr-CA"
                self.assertEqual(page.html_lang, expected_lang)
                if path == "/fr/confidentialite/":
                    self.assertIsNone(page.description)
                else:
                    self.assertTrue(page.description)


class TestNoLeaks(unittest.TestCase):
    """Planted words must appear only on the page of their case."""

    PLANTED = {
        "email": "/fr/contact/",
        "mail": "/fr/confidentialite/",
        "parking": "/fr/contact/",
        "week-end": "/fr/",
        "shopping": "/fr/blogue/lancement/",
        "Add to cart": "/fr/produits/melange-maison/",
        "This field is required": "/fr/contact/",
        "Woman holding a coffee cup": "/fr/",
    }

    def test_planted_words_do_not_leak(self):
        for word, home in self.PLANTED.items():
            for path, page in FR_PAGES.items():
                if path == home:
                    continue
                with self.subTest(word=word, page=path):
                    self.assertFalse(has_word(page.all_text, word))


class TestLinks(unittest.TestCase):
    def test_internal_links_resolve(self):
        for path, page in PAGES.items():
            for href in page.links + list(page.hreflang.values()):
                if href.startswith(("http", "#", "mailto:")):
                    continue
                with self.subTest(page=path, href=href):
                    self.assertTrue(url_to_file(href).exists())


if __name__ == "__main__":
    unittest.main()
