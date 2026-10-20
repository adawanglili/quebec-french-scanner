"""Extract text units from a page and decide whether a string is English.

A text unit is one piece of text a visitor can see or hear: the direct text of
an element, or an attribute such as alt, placeholder or aria-label. Inline
elements like <em> get their own unit, so an English title inside a French
sentence is found on its own.

Language decision:
  * Long strings (6 words or more) use Lingua.
  * Short strings, like buttons and menu items, are too short for Lingua
    alone. "Contact us" scores only 54% English. They also use word
    frequency: each word leans English, leans French or is neutral, based on
    how common it is in each language (wordfreq).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from lingua import Language, LanguageDetectorBuilder
from wordfreq import tokenize, zipf_frequency

SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "head", "title", "meta", "link"}
LANDMARKS = ("nav", "header", "footer", "aside", "form", "main", "article")
QUOTE_TAGS = {"em", "i", "cite", "q"}
TEXT_ATTRIBUTES = ("alt", "placeholder", "aria-label", "title")
BUTTON_INPUT_TYPES = {"submit", "button", "reset"}

LONG_STRING_WORDS = 6
LONG_STRING_CONFIDENCE = 0.9
WORD_MARGIN = 1.0  # zipf difference needed for a word to lean one way

EMAIL = re.compile(r"\S+@\S+")
URL = re.compile(r"https?://\S+|www\.\S+")
HAS_DIGIT = re.compile(r"\d")
FILE_NAME = re.compile(r"\.(png|jpe?g|gif|webp|svg|avif|bmp|tiff?)$", re.IGNORECASE)


@dataclass
class TextUnit:
    text: str
    element: str  # short description, like "nav a" or "img@alt"
    tag: str
    kind: str  # "text" or the attribute name


@dataclass
class LanguageVerdict:
    is_english: bool
    english_confidence: float
    english_words: int
    french_words: int
    words: int


@lru_cache(maxsize=1)
def detector():
    return (
        LanguageDetectorBuilder.from_languages(Language.ENGLISH, Language.FRENCH)
        .with_preloaded_language_models()
        .build()
    )


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def declared_english(el: Tag) -> bool:
    """True if the element or an ancestor carries lang="en..."."""
    for node in [el, *el.parents]:
        if isinstance(node, Tag) and node.name != "html" and node.get("lang"):
            return node["lang"].lower().startswith("en")
    return False


def describe(el: Tag) -> str:
    landmark = next((p.name for p in el.parents if isinstance(p, Tag) and p.name in LANDMARKS), None)
    name = el.name
    classes = el.get("class")
    if classes:
        name += "." + ".".join(classes)
    return f"{landmark} {name}" if landmark and landmark != el.name else name


def extract_units(html: str) -> list[TextUnit]:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.body or soup
    units: list[TextUnit] = []
    for el in body.find_all(True):
        if el.name in SKIP_TAGS or any(p.name in SKIP_TAGS for p in el.parents if isinstance(p, Tag)):
            continue
        if declared_english(el):
            continue
        direct = clean(
            " ".join(
                str(c) for c in el.children
                if isinstance(c, NavigableString) and not isinstance(c, Comment)
            )
        )
        if direct:
            units.append(TextUnit(direct, describe(el), el.name, "text"))
        for attr in TEXT_ATTRIBUTES:
            value = clean(el.get(attr) or "")
            if value and not FILE_NAME.search(value):  # an image file name is not text to translate
                units.append(TextUnit(value, f"{describe(el)}@{attr}", el.name, attr))
        if el.name == "input" and (el.get("type") or "").lower() in BUTTON_INPUT_TYPES:
            value = clean(el.get("value") or "")
            if value:
                units.append(TextUnit(value, f"{describe(el)}@value", el.name, "value"))
    return units


# ---------------------------------------------------------------------------
# Language decision
# ---------------------------------------------------------------------------

def words_for_detection(text: str, brand_words: set[str]) -> list[str]:
    """Words left after removing emails, URLs, codes, numbers and brand names."""
    text = URL.sub(" ", EMAIL.sub(" ", text))
    words = []
    for raw in text.split():
        if HAS_DIGIT.search(raw):
            continue  # product codes, prices, dates
        for token in tokenize(raw, "fr"):
            if any(c.isalpha() for c in token) and token.lower() not in brand_words:
                words.append(token.lower())
    return words


def word_lean(word: str) -> int:
    """+1 if the word leans English, -1 if it leans French, 0 if neutral."""
    margin = zipf_frequency(word, "en") - zipf_frequency(word, "fr")
    if margin >= WORD_MARGIN:
        return 1
    if margin <= -WORD_MARGIN:
        return -1
    return 0


def judge_language(text: str, brand_words: set[str] | None = None) -> LanguageVerdict | None:
    """Return a verdict, or None when nothing is left to judge."""
    words = words_for_detection(text, brand_words or set())
    if not words:
        return None
    sample = " ".join(words)
    confidence = detector().compute_language_confidence(sample, Language.ENGLISH)
    leans = [word_lean(w) for w in words]
    en_words = sum(1 for x in leans if x > 0)
    fr_words = sum(1 for x in leans if x < 0)
    if len(words) >= LONG_STRING_WORDS:
        is_english = confidence >= LONG_STRING_CONFIDENCE
    else:
        # Single letters like the "d" in "d'expiration" count as French.
        is_english = en_words >= 1 and fr_words == 0 and confidence >= 0.5
    return LanguageVerdict(is_english, round(confidence, 3), en_words, fr_words, len(words))


def brand_words_from(texts: list[str]) -> set[str]:
    words = set()
    for text in texts:
        for token in tokenize(text, "fr"):
            if any(c.isalpha() for c in token):
                words.add(token.lower())
    return words
