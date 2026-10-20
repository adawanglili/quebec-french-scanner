"""Terminology check: common web anglicisms on French pages.

The term list (lexicon/web_terms.csv) is our own curated list. Each entry
has the forms to look for on French pages, the Quebec French suggestion and
the English words used to find the matching record in the OQLF Grand
dictionnaire terminologique (GDT).

At scan time each entry is resolved to a GDT record from the downloaded
OQLF data in data/raw/. The record link goes on the finding as evidence. If
the data is missing or no record matches, the finding is still reported but
as "needs review", because it has no citation.

Kinds:
  flag       report as a finding
  tolerated  common in Quebec usage, report as needs review
  review     depends on context, report as needs review
  france     France French term found in the GDT, report as needs review

France French terms are also taken straight from the GDT: records that label
one term [France] and another [Québec/Canada]. Only terms of two words or
more are used. Single words like "menu" or "président" have other common
meanings and would cause false alarms.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEXICON = Path(__file__).resolve().parent / "lexicon" / "web_terms.csv"
DATA_DIR = ROOT / "data" / "raw"
PREFERRED_LABELS = {"Québec/Canada", "Québec", "recommandé", "normalisé"}
FRANCE_LABELS = {"France", "France/Europe", "France,Belgique", "Europe"}
QUEBEC_LABELS = {"Québec/Canada", "Québec", "Canada"}


@dataclass
class TermEntry:
    forms: list[str]
    suggestion: str | None
    lookup_en: list[str]
    kind: str
    note: str
    pattern: re.Pattern = field(repr=False, default=None)
    gdt_record: str | None = None
    gdt_terms: str | None = None


@dataclass
class TermMatch:
    entry: TermEntry
    form: str  # the text found on the page
    context: str


def split_terms(cell: str) -> list[tuple[str, list[str]]]:
    """'courriel (n. m.) [Québec];mail (n. m.)' -> [('courriel', ['Québec']), ('mail', [])]"""
    out = []
    for raw in (cell or "").split(";"):
        labels = re.findall(r"\[([^\]]+)\]", raw)
        term = re.sub(r"\s*(\([^)]*\)|\[[^\]]*\])", "", raw).strip().lower()
        if term:
            out.append((term, labels))
    return out


def find_records_file(data_dir: Path = DATA_DIR) -> Path | None:
    manifest = data_dir / "MANIFEST.json"
    if manifest.exists():
        info = json.loads(manifest.read_text(encoding="utf-8")).get("files", {}).get("records")
        if info and (data_dir / info["file"]).exists():
            return data_dir / info["file"]
    files = sorted(data_dir.glob("fiches_*.csv"))
    return files[-1] if files else None


def resolve(entries: list[TermEntry], rows: list[dict]) -> None:
    """Attach the best GDT record to each entry, in place."""
    if not rows:
        return
    parsed = [(split_terms(r["Termes_francais"]), {t for t, _ in split_terms(r["Termes_anglais"])}, r) for r in rows]
    for entry in entries:
        wanted_en = {w.lower() for w in entry.lookup_en}
        # With no suggestion (review entries), cite the record of the term itself.
        target = (entry.suggestion or entry.forms[-1]).lower()
        candidates = []
        for fr, en, row in parsed:
            fr_terms = [t for t, _ in fr]
            en_hit = bool(wanted_en & en)
            if target not in fr_terms or not (en_hit or entry.suggestion):
                continue
            labels = dict(fr).get(target, [])
            rank = (
                en_hit,
                fr_terms[0] == target,
                bool(PREFERRED_LABELS & set(labels)),
                row["Date_fiche"],
            )
            candidates.append((rank, row))
        if candidates:
            best = max(candidates, key=lambda c: c[0])[1]
            entry.gdt_record = best["URL_fiche"]
            entry.gdt_terms = best["Termes_francais"]


def read_records(records_file: Path | None) -> list[dict]:
    if not records_file:
        return []
    with records_file.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def france_entries(rows: list[dict], known_forms: set[str]) -> list[TermEntry]:
    """France French terms (two words or more) with their Quebec equivalent."""
    entries: dict[str, TermEntry] = {}
    for row in rows:
        terms = split_terms(row["Termes_francais"])
        quebec = [t for t, labels in terms if QUEBEC_LABELS & set(labels)]
        if not quebec:
            continue
        for term, labels in terms:
            if not FRANCE_LABELS & set(labels) or len(term.split()) < 2:
                continue
            if term in known_forms or term in quebec or term in entries:
                continue
            entries[term] = TermEntry(
                forms=[term],
                suggestion=quebec[0],
                lookup_en=[],
                kind="france",
                note="Labelled France usage in the GDT. The same record gives the Quebec term.",
                pattern=re.compile(rf"(?<![\w-]){re.escape(term)}(?![\w-])", re.IGNORECASE),
                gdt_record=row["URL_fiche"] or None,
                gdt_terms=row["Termes_francais"],
            )
    return list(entries.values())


@lru_cache(maxsize=1)
def load_lexicon(lexicon: Path = LEXICON, data_dir: Path = DATA_DIR) -> tuple[TermEntry, ...]:
    entries = []
    with lexicon.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            forms = sorted({f.strip() for f in row["pattern"].split("|") if f.strip()}, key=len, reverse=True)
            alternation = "|".join(re.escape(f) for f in forms)
            entries.append(TermEntry(
                forms=forms,
                suggestion=row["suggestion"].strip() or None,
                lookup_en=[w.strip() for w in row["lookup_en"].split("|") if w.strip()],
                kind=row["kind"].strip(),
                note=row["note"].strip(),
                pattern=re.compile(rf"(?<![\w-])(?:{alternation})(?![\w-])", re.IGNORECASE),
            ))
    rows = read_records(find_records_file(data_dir))
    resolve(entries, rows)
    entries += france_entries(rows, {f.lower() for e in entries for f in e.forms})
    # Longest forms first, so "faire du shopping" wins over "shopping".
    entries.sort(key=lambda e: -max(len(f) for f in e.forms))
    return tuple(entries)


def find_terms(text: str, entries: tuple[TermEntry, ...]) -> list[TermMatch]:
    """Return term matches in text. A span matched once is not matched again."""
    text = text.replace("’", "'")  # curly apostrophe, same length
    taken: list[tuple[int, int]] = []
    found = []
    for entry in entries:
        for m in entry.pattern.finditer(text):
            if any(m.start() < end and start < m.end() for start, end in taken):
                continue
            taken.append((m.start(), m.end()))
            lo, hi = max(0, m.start() - 60), min(len(text), m.end() + 60)
            found.append(TermMatch(entry, m.group(0), text[lo:hi].strip()))
    return found
