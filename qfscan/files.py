"""Scan web pages saved from a browser instead of fetching them.

Use this for sites that block automated tools. Open each page in your
browser and save it (Ctrl+S, "Webpage, complete"). Chrome saves the page as
you see it, so text added by JavaScript is included.

Each saved file needs its original address, so links between English and
French pages can be matched. The address is taken from, in order:
  1. the "saved from url" comment that browsers add
  2. the canonical link of the page
  3. the og:url meta tag
  4. the file's path inside the folder you scan
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .crawl import CrawlResult, normalize_url, pair_pages, parse_page

HTML_SUFFIXES = {".html", ".htm"}
LOCAL_BASE = "https://saved-pages.local"
SAVED_FROM = re.compile(r"<!--\s*saved from url=\(\d+\)(\S+?)\s*-->", re.IGNORECASE)
META_CHARSET = re.compile(rb"""<meta[^>]+charset=["']?([\w-]+)""", re.IGNORECASE)


def decode(raw: bytes) -> str:
    match = META_CHARSET.search(raw[:4096])
    declared = [match.group(1).decode("ascii", "ignore")] if match else []
    for encoding in [*declared, "utf-8", "cp1252"]:
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace")


def original_url(html: str, fallback: str) -> str:
    match = SAVED_FROM.search(html[:2000])
    if match and match.group(1).startswith("http"):
        return normalize_url(match.group(1))
    soup = BeautifulSoup(html[:200_000], "html.parser")
    canonical = soup.find("link", rel="canonical", href=True)
    if canonical and canonical["href"].startswith("http"):
        return normalize_url(canonical["href"])
    og = soup.find("meta", attrs={"property": "og:url"})
    if og and (og.get("content") or "").startswith("http"):
        return normalize_url(og["content"])
    return normalize_url(fallback)


def path_url(path: str) -> str:
    """'fr/a-propos/index.html' -> 'https://saved-pages.local/fr/a-propos/'"""
    path = path.replace("\\", "/").lstrip("/")
    if path.endswith(("index.html", "index.htm")):
        path = path.rsplit("/", 1)[0] + "/" if "/" in path else ""
    return urljoin(LOCAL_BASE + "/", path)


def find_html_files(paths: list[Path]) -> list[tuple[Path, str]]:
    """Return (file, path relative to the folder given) for every saved page."""
    found = []
    for root in paths:
        if root.is_file() and root.suffix.lower() in HTML_SUFFIXES:
            found.append((root, root.name))
        elif root.is_dir():
            for file in sorted(root.rglob("*")):
                # Skip the "Page_files" folders browsers create for images and scripts.
                if any(part.endswith("_files") for part in file.relative_to(root).parts[:-1]):
                    continue
                if file.is_file() and file.suffix.lower() in HTML_SUFFIXES:
                    found.append((file, file.relative_to(root).as_posix()))
    return found


def scan_saved_pages(pages: list[tuple[str, str]]) -> CrawlResult:
    """Build a crawl result from (relative path, html) pairs."""
    result_pages = {}
    for rel_path, html in pages:
        url = original_url(html, path_url(rel_path))
        if url not in result_pages:
            result_pages[url] = parse_page(url, 200, html)
    start = next(iter(result_pages), LOCAL_BASE + "/")
    return CrawlResult(
        start_url=start,
        pages=result_pages,
        pairs=pair_pages(result_pages),
        skipped=[],
        hit_page_cap=False,
    )


def load_saved_pages(paths: list[Path]) -> CrawlResult:
    return scan_saved_pages([(rel, decode(file.read_bytes())) for file, rel in find_html_files(paths)])
