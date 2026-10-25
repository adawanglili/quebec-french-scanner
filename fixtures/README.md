# Fixture site

Northwind is a fake bilingual coffee shop site with planted French language gaps. It gives the scanner a ground truth to measure against and a demo that always works.

## Run it

```bash
python fixtures/build_fixture.py              # rebuild fixtures/site/ from the page content
python -m http.server 8000 -d fixtures/site   # serve it at http://localhost:8000
python -m unittest discover tests             # check the fixture against expected.json
```

The generated `site/` folder is committed, so you can serve it without building. Edit `build_fixture.py`, not the HTML, then rebuild.

## Pages

| Page | English | French |
| --- | --- | --- |
| Home | `/en/` | `/fr/` |
| Products | `/en/products/` | `/fr/produits/` |
| Product detail | `/en/products/house-blend/` | `/fr/produits/melange-maison/` |
| Cart and payment | `/en/checkout/` | `/fr/paiement/` |
| About | `/en/about/` | `/fr/a-propos/` |
| Contact | `/en/contact/` | `/fr/contact/` |
| Privacy | `/en/privacy/` | `/fr/confidentialite/` |
| Terms | `/en/terms/` | `/fr/conditions/` |
| Blog post | `/en/blog/launch/` | `/fr/blogue/lancement/` |
| Careers | `/en/careers/` | none |

Pairs are linked with hreflang, except the blog post, which is linked only by the language switcher. The root page `/` is a simple language chooser.

## Planted cases

The full list with expected results is in [`expected.json`](expected.json). Each case is also marked in the HTML with a comment such as `<!-- case: LE-01 -->`. The scanner must ignore these comments.

| ID | Page | What is planted | Expected |
| --- | --- | --- | --- |
| MP-01 | `/en/careers/` | No French version | Flag |
| MP-02 | `/en/about/` | Paired with `/fr/a-propos/` by hreflang | No finding |
| MP-03 | `/en/blog/launch/` | Paired by switcher link only | No finding |
| LE-01 | `/fr/produits/melange-maison/` | Button "Add to cart" | Flag |
| LE-02 | All French pages | Nav item "Contact us" | Flag, once |
| LE-03 | `/fr/contact/` | Error "This field is required" | Flag |
| LE-04 | `/fr/` | Alt text "Woman holding a coffee cup" | Flag |
| LE-05 | All French pages | English footer paragraph | Flag, once |
| LE-06 | All French pages | Brand name "Northwind" | No finding |
| LE-07 | `/fr/contact/` | "par email" | Needs review |
| LE-08 | `/fr/produits/melange-maison/` | Product code "SKU-4471" | No finding |
| LE-09 | `/fr/blogue/lancement/` | English book title in italics | Needs review |
| MD-01 | `/fr/conditions/` | `<html lang="en">` | Flag |
| MD-02 | `/fr/produits/` | English title | Flag |
| MD-03 | `/fr/confidentialite/` | No meta description | No finding. Out of scope, an SEO issue |
| MD-04 | `/fr/blogue/lancement/` | English meta description | Flag |
| MD-05 | `/fr/a-propos/` | Correct lang, title and description | No finding |
| TM-01 | `/fr/paiement/` | "panier d'achat" | No finding |
| TM-02 | `/fr/confidentialite/` | "un mail" | Needs review, suggest "courriel". *Mail* also names shopping centres in Quebec |
| TM-03 | `/fr/contact/` | "Parking" | Flag, suggest "stationnement" |
| TM-04 | `/fr/` | "le week-end" | Flag, suggest "fin de semaine" |
| TM-05 | `/fr/blogue/lancement/` | "faire du shopping" | Flag, suggest "magasiner" |
| TM-06 | `/fr/produits/melange-maison/` | "Télécharger" | No finding |
| TM-07 | `/fr/paiement/` | "Date d'expiration" | Needs review |

## Rules for editing

- Everything that is not a planted case must be clean Quebec French. Any other finding counts as a false positive.
- The tests check that planted words such as "parking" or "week-end" appear only on their own page. Add new planted words to `TestNoLeaks` in `tests/test_fixture.py`.
- The French language switcher reads "English" and carries `lang="en"`. This is correct markup, not a gap.
- Each terminology case has a `gdt_record` link in `expected.json`. They were checked against the term records file of 2026-01-19.
