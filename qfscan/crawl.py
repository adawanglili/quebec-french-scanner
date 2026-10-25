"""Crawl one site and pair its English and French pages.

The crawler fetches static HTML only. It stays on the start host, respects
robots.txt and stops at a page cap. JavaScript is not run.

Pairing order for each English page:
  1. hreflang alternates (either direction)
  2. the language switcher link (either direction)
An English page with neither has no French equivalent.
"""

from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass, field
from urllib import robotparser
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

from . import __version__

USER_AGENT = f"qfscan/{__version__} (+https://github.com/adawanglili/quebec-french-scanner)"
# Ask for Quebec French, like a browser set to French. Sites that pick the
# language from this header then serve the French pages.
ACCEPT_LANGUAGE = "fr-CA,fr;q=0.9,en;q=0.5"
REQUEST_HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": ACCEPT_LANGUAGE}
DEFAULT_MAX_PAGES = 50

SKIP_EXTENSIONS = {
    ".css", ".js", ".json", ".xml", ".txt", ".pdf", ".zip", ".gz",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".avif",
    ".mp3", ".mp4", ".webm", ".mov", ".woff", ".woff2", ".ttf", ".eot",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv",
}

# Link text that marks a language switcher, by target language.
SWITCHER_TEXT = {
    "fr": {"français", "francais", "fr", "version française", "en français"},
    "en": {"english", "anglais", "en", "english version", "in english"},
}


@dataclass
class Page:
    url: str
    status: int
    html: str = field(default="", repr=False)
    html_lang: str | None = None
    title: str | None = None
    description: str | None = None
    alternates: dict[str, str] = field(default_factory=dict)  # hreflang code -> url
    switcher: dict[str, str] = field(default_factory=dict)  # "en" or "fr" -> url
    links: list[str] = field(default_factory=list)
    language: str | None = None
    language_source: str | None = None
    canonical: str | None = None

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "status": self.status,
            "language": self.language,
            "language_source": self.language_source,
            "html_lang": self.html_lang,
            "title": self.title,
            "description": self.description,
            "alternates": self.alternates,
            "switcher": self.switcher,
        }


@dataclass
class Pair:
    en: str
    fr: str | None
    method: str  # "hreflang", "switcher", "not_crawled" or "none"

    def to_dict(self) -> dict:
        return {"en": self.en, "fr": self.fr, "method": self.method}


@dataclass
class CrawlResult:
    start_url: str
    pages: dict[str, Page]
    pairs: list[Pair]
    skipped: list[dict]
    hit_page_cap: bool
    start_redirect: str | None = None

    def to_dict(self) -> dict:
        return {
            "start_url": self.start_url,
            "page_count": len(self.pages),
            "hit_page_cap": self.hit_page_cap,
            "start_redirect": self.start_redirect,
            "pages": [p.to_dict() for p in self.pages.values()],
            "pairs": [p.to_dict() for p in self.pairs],
            "skipped": self.skipped,
        }


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """Lowercase scheme and host, drop the fragment, default the path to /."""
    parts = urlsplit(url)
    path = parts.path or "/"
    query = "&".join(
        pair for pair in parts.query.split("&")
        if pair and not TRACKING_PARAMS.match(pair.split("=", 1)[0])
    )
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


TRACKING_PARAMS = re.compile(r"^(utm_\w+|gclid|fbclid|mc_cid|mc_eid)$", re.I)


def duplicate_of(page: Page, pages: dict) -> str | None:
    """Return the crawled URL this page duplicates, or None.

    A page is a duplicate when its canonical link, or the hreflang link for its
    own language, points to another page we already crawled. This catches the
    same page reached with a tracking parameter, like ?navigMW=pp.
    """
    candidates = []
    if page.canonical:
        candidates.append(page.canonical)
    lang = page.language
    for code, href in page.alternates.items():
        if lang and primary_language(code) == lang:
            candidates.append(href)
    for target in candidates:
        if target != page.url and target in pages:
            return target
    return None


def same_site(url: str, start: str) -> bool:
    host = urlsplit(url).netloc.lower().removeprefix("www.")
    return host == urlsplit(start).netloc.lower().removeprefix("www.")


def looks_like_html(url: str) -> bool:
    path = urlsplit(url).path.lower()
    dot = path.rfind(".")
    return dot == -1 or path[dot:] not in SKIP_EXTENSIONS or path.endswith((".html", ".htm"))


def primary_language(code: str | None) -> str | None:
    """'fr-CA' -> 'fr'. Returns None for empty or x-default."""
    if not code or code.lower() == "x-default":
        return None
    return code.split("-")[0].split("_")[0].lower()


URL_LANG_PATTERNS = [
    re.compile(r"^/(fr|en)(?:[-_][a-z]{2})?(?:/|$)", re.I),  # /fr/, /fr-ca/
    re.compile(r"[?&](?:lang|locale|hl)=(fr|en)", re.I),  # ?lang=fr
]


def language_from_url(url: str) -> str | None:
    parts = urlsplit(url)
    host = parts.netloc.lower()
    if host.startswith(("fr.", "en.")):
        return host[:2]
    for pattern in URL_LANG_PATTERNS:
        target = parts.path if pattern is URL_LANG_PATTERNS[0] else "?" + parts.query
        match = pattern.search(target)
        if match:
            return match.group(1).lower()
    return None


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_page(url: str, status: int, html: str) -> Page:
    soup = BeautifulSoup(html, "html.parser")
    page = Page(url=url, status=status, html=html)

    html_tag = soup.find("html")
    page.html_lang = html_tag.get("lang") if html_tag else None
    if soup.title and soup.title.string is not None:
        page.title = soup.title.string.strip()
    meta = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    if meta is not None:
        page.description = (meta.get("content") or "").strip()

    for link in soup.find_all("link", rel="alternate", hreflang=True, href=True):
        page.alternates[link["hreflang"].strip()] = normalize_url(urljoin(url, link["href"]))
    canonical = soup.find("link", rel="canonical", href=True)
    if canonical is not None:
        page.canonical = normalize_url(urljoin(url, canonical["href"]))

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        target = normalize_url(urljoin(url, href))
        page.links.append(target)
        lang = switcher_language(a)
        if lang and target != url and lang not in page.switcher:
            page.switcher[lang] = target

    page.language, page.language_source = infer_language(page)
    return page


def switcher_language(a) -> str | None:
    """Return 'en' or 'fr' if this anchor looks like a language switcher."""
    hreflang = primary_language(a.get("hreflang"))
    if hreflang in ("en", "fr"):
        return hreflang
    text = a.get_text(" ", strip=True).lower()
    for lang, words in SWITCHER_TEXT.items():
        if text in words:
            return lang
    return None


def infer_language(page: Page) -> tuple[str | None, str | None]:
    """Decide the page language for pairing.

    The html lang attribute comes last on purpose: a wrong lang attribute is
    one of the gaps we report, so it should not decide the pairing.
    """
    for code, href in page.alternates.items():
        lang = primary_language(code)
        if href == page.url and lang:
            return lang, "hreflang"
    lang = language_from_url(page.url)
    if lang:
        return lang, "url"
    lang = primary_language(page.html_lang)
    if lang:
        return lang, "html_lang"
    return None, None


# ---------------------------------------------------------------------------
# Crawl
# ---------------------------------------------------------------------------

def load_robots(client: httpx.Client, start_url: str) -> robotparser.RobotFileParser:
    parts = urlsplit(start_url)
    robots_url = urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
    parser = robotparser.RobotFileParser()
    try:
        response = client.get(robots_url, headers=REQUEST_HEADERS)
        lines = response.text.splitlines() if response.status_code == 200 else []
    except httpx.HTTPError:
        lines = []
    parser.parse(lines)
    return parser


def crawl(
    start_url: str,
    max_pages: int = DEFAULT_MAX_PAGES,
    delay: float = 0.5,
    respect_robots: bool = True,
    client: httpx.Client | None = None,
    progress=None,
) -> CrawlResult:
    """Breadth first crawl from start_url, then pair the pages."""
    start_url = normalize_url(start_url)
    own_client = client is None
    client = client or httpx.Client(
        headers=REQUEST_HEADERS, follow_redirects=True, timeout=20.0
    )
    pages: dict[str, Page] = {}
    skipped: list[dict] = []
    # Two queues. French pages go first, so the page limit is spent on the
    # pages we check, not on English pages that only point to them.
    french_queue: deque[str] = deque()
    queue: deque[str] = deque([start_url])
    seen: set[str] = {start_url}
    start_redirect = None
    hit_cap = False

    try:
        robots = load_robots(client, start_url) if respect_robots else None
        while french_queue or queue:
            if len(pages) >= max_pages:
                hit_cap = True
                break
            url = french_queue.popleft() if french_queue else queue.popleft()
            if robots and not robots.can_fetch(USER_AGENT, url):
                skipped.append({"url": url, "reason": "robots.txt"})
                continue
            try:
                response = client.get(url, headers=REQUEST_HEADERS)
            except httpx.HTTPError as error:
                skipped.append({"url": url, "reason": f"error: {error.__class__.__name__}"})
                continue
            final_url = normalize_url(str(response.url))
            if not same_site(final_url, start_url):
                skipped.append({"url": url, "reason": f"redirects off site to {final_url}"})
                continue
            content_type = response.headers.get("content-type", "")
            if response.status_code == 200 and "html" not in content_type:
                skipped.append({"url": url, "reason": f"not HTML ({content_type})"})
                continue
            if final_url in pages:
                continue
            html = response.text if response.status_code == 200 else ""
            page = parse_page(final_url, response.status_code, html)
            original = duplicate_of(page, pages)
            if original:
                skipped.append({"url": final_url, "reason": f"same page as {original}"})
                continue
            pages[final_url] = page
            if progress:
                progress(len(pages), max_pages, final_url)

            if url == start_url and final_url != start_url:
                start_redirect = final_url
            french_targets = {
                href for code, href in page.alternates.items() if primary_language(code) == "fr"
            }
            if page.switcher.get("fr"):
                french_targets.add(page.switcher["fr"])
            for target in [*page.alternates.values(), *page.links]:
                if target not in seen and same_site(target, start_url) and looks_like_html(target):
                    seen.add(target)
                    if target in french_targets or language_from_url(target) == "fr":
                        french_queue.append(target)
                    else:
                        queue.append(target)
            if delay and (queue or french_queue):
                time.sleep(delay)
    finally:
        if own_client:
            client.close()

    return CrawlResult(
        start_url=start_url,
        pages=pages,
        pairs=pair_pages(pages),
        skipped=skipped,
        hit_page_cap=hit_cap,
        start_redirect=start_redirect,
    )


# ---------------------------------------------------------------------------
# Pairing
# ---------------------------------------------------------------------------

def pair_pages(pages: dict[str, Page]) -> list[Pair]:
    ok = {url: p for url, p in pages.items() if p.status == 200}
    en_pages = [p for p in ok.values() if p.language == "en"]
    fr_pages = [p for p in ok.values() if p.language == "fr"]

    def is_fr(url: str | None) -> bool:
        return url in ok and ok[url].language == "fr"

    pairs = []
    for en in en_pages:
        fr_url, method = None, "none"
        for code, href in en.alternates.items():
            if primary_language(code) == "fr" and is_fr(href):
                fr_url, method = href, "hreflang"
                break
        if not fr_url:
            for fr in fr_pages:
                if any(primary_language(c) == "en" and h == en.url for c, h in fr.alternates.items()):
                    fr_url, method = fr.url, "hreflang"
                    break
        if not fr_url and is_fr(en.switcher.get("fr")):
            fr_url, method = en.switcher["fr"], "switcher"
        if not fr_url:
            for fr in fr_pages:
                if fr.switcher.get("en") == en.url:
                    fr_url, method = fr.url, "switcher"
                    break
        if not fr_url:
            # A French page is linked but the crawl stopped before reaching it.
            # We cannot say it is missing, so it is not reported.
            linked = [h for c, h in en.alternates.items() if primary_language(c) == "fr"]
            linked += [en.switcher["fr"]] if en.switcher.get("fr") else []
            unvisited = [h for h in linked if h not in pages]
            if unvisited:
                fr_url, method = unvisited[0], "not_crawled"
        pairs.append(Pair(en=en.url, fr=fr_url, method=method))
    return pairs
