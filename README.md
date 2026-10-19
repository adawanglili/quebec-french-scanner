# Quebec French Website Scanner

A language gap scanner for websites that serve Quebec. It finds pages and strings that may not meet French language expectations, explains each one and points to the rule or term record behind it.

The scanner supports human review. It does not give legal advice and it never says a site is "compliant." Results are risk findings or items that need review.

This is a portfolio project by Lili Wang. It is a working prototype, not a product.

## Status

Week 1 of 3. The fixture site and the data download script are done. The crawler and checks are next.

## What it checks

| Check | What it does |
| --- | --- |
| Missing French page | An English page has no French equivalent |
| Leftover English | English strings on French pages: buttons, menus, errors, alt text |
| Metadata | Missing or English title and description, wrong `lang`, hreflang |
| OQLF terminology | Common web terms checked against OQLF officialized terms, with the record cited |

Only flagged terminology snippets go to a language model for a confirm or reject step. Everything else is deterministic.

## Repo layout

```
fixtures/
  build_fixture.py   builds the fake bilingual test site
  site/              the built site, served as a web root
  expected.json      ground truth for the 24 planted cases
scripts/
  download_oqlf_data.py   fetches the OQLF data into data/raw/
tests/
  test_fixture.py    checks the fixture against expected.json
data/raw/            downloaded data (not committed)
```

## Quick start

Requires Python 3.10 or later. The current scripts use only the standard library.

```bash
# Get the OQLF data
python scripts/download_oqlf_data.py

# Serve the fixture site at http://localhost:8000
python -m http.server 8000 -d fixtures/site

# Check the fixture
python -m unittest discover tests
```

## Data sources

The scanner uses open terminology data. The data files are not in this repo. Run `scripts/download_oqlf_data.py` to fetch them into `data/raw/`.

They are kept out of the repo for three reasons:

1. **License.** The OQLF data is licensed CC BY-NC-SA 4.0. Copies must keep the attribution and the same license. Linking to the source is cleaner than redistributing it next to MIT code.
2. **Freshness.** The OQLF publishes new files with the release date in the name. The script asks the Données Québec API for the current files, so you always get the latest version.
3. **Size.** The term records file alone is about 20 MB.

The script writes `data/raw/MANIFEST.json` with the URL, size, SHA-256 and download time of each file. A scan report can then say exactly which data it used.

| Dataset | Script name | Publisher | Size | License | Used for |
| --- | --- | --- | --- | --- | --- |
| [Termes officialisés](https://www.donneesquebec.ca/recherche/dataset/donnees-linguistiques/resource/882453c2-93c3-4204-b5ff-6d6297082ad9) (Grand dictionnaire terminologique) | `terms` | OQLF | 1 MB | CC BY-NC-SA 4.0 | Terminology check |
| [Fiches terminologiques](https://www.donneesquebec.ca/recherche/dataset/donnees-linguistiques/resource/c3ce0af4-7c0f-4dd2-b53a-6dc7fb3ea5ef) (Grand dictionnaire terminologique) | `records` | OQLF | 20 MB | CC BY-NC-SA 4.0 | Record citations and suggested terms |
| [Phrases grammaticales et agrammaticales](https://www.donneesquebec.ca/recherche/dataset/donnees-linguistiques/resource/f91f62f6-2bed-4bf1-891b-51255bf5fbba) (Banque de dépannage linguistique) | `bdl` | OQLF | 6 MB | CC BY-NC-SA 4.0 | Possible test sentences |

Download one dataset only with `--only`, for example `--only terms`. Download again with `--force`.

**Attribution.** Source : Office québécois de la langue française, Vitrine linguistique. Données diffusées sur [Données Québec](https://www.donneesquebec.ca/recherche/dataset/donnees-linguistiques) sous licence [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).

**Noncommercial use.** This project is a noncommercial portfolio prototype, which the license allows. Any commercial use of the OQLF data would need permission from the OQLF.

**Planned sources.** TERMIUM Plus (Government of Canada) and the Dictionnaire des francophones may be added later. Their licenses still need to be checked.

## License

The code in this repo is under the [MIT License](LICENSE). The OQLF data keeps its own license, described above.
