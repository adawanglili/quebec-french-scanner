"""Terminology check tests.

Matching tests run anywhere. Tests that need GDT records are skipped when the
OQLF data has not been downloaded (python scripts/download_oqlf_data.py).
"""

from __future__ import annotations

import pytest

from qfscan.terms import find_records_file, find_terms, load_lexicon

HAS_DATA = find_records_file() is not None
needs_data = pytest.mark.skipif(not HAS_DATA, reason="OQLF data not downloaded")


def forms(text: str) -> list[tuple[str, str | None]]:
    return [(m.form, m.entry.suggestion) for m in find_terms(text, load_lexicon())]


def test_email_is_not_matched_as_mail():
    assert forms("Écrivez-nous par email.") == [("email", "courriel")]
    assert forms("Envoyez un e-mail.") == [("e-mail", "courriel")]
    assert forms("Envoyez un mail.") == [("mail", "courriel")]


def test_longest_form_wins():
    assert forms("Plus besoin d'aller faire du shopping.") == [("faire du shopping", "magasiner")]
    assert forms("Le shopping du samedi.") == [("shopping", "magasinage")]


def test_case_and_plural():
    assert forms("Parking gratuit. Deux parkings.") == [("Parking", "stationnement"), ("parkings", "stationnement")]


def test_curly_apostrophe():
    assert forms("Date d’expiration") == [("Date d'expiration", None)]


def test_no_match_in_clean_quebec_french():
    text = "Votre panier d'achat. Télécharger le guide. Adresse courriel. Fin de semaine. Stationnement gratuit."
    assert forms(text) == []


@needs_data
def test_every_entry_has_a_gdt_record():
    unresolved = [e.forms[0] for e in load_lexicon() if not e.gdt_record]
    assert unresolved == []


@needs_data
@pytest.mark.parametrize(
    "form, record",
    [
        ("mail", "8353974"),
        ("parking", "1298970"),
        ("week-end", "8361442"),
        ("faire du shopping", "8357752"),
        ("date d'expiration", "8426438"),
    ],
)
def test_records_match_expected(form, record):
    entry = next(e for e in load_lexicon() if form in e.forms)
    assert f"/fiche/{record}/" in entry.gdt_record


@needs_data
def test_france_terms_from_gdt():
    assert forms("Appelez notre numéro vert.") == [("numéro vert", "numéro sans frais")]
    assert forms("Rangez-le dans un abri de jardin.") == [("abri de jardin", "cabanon")]


def test_single_words_with_other_meanings_are_not_matched():
    assert forms("Consultez le menu du jour. Le président parle.") == []


def test_curated_france_usage():
    assert forms("Notre tchat est ouvert.") == [("tchat", "clavardage")]


def test_mail_goes_to_review():
    # "mail" usually means courriel, but in Quebec it also names shopping centres.
    matches = find_terms("Rendez-vous au Mail Champlain.", load_lexicon())
    assert [(m.form, m.entry.kind) for m in matches] == [("Mail", "review")]
