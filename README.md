# Quebec French Website Scanner

A language gap scanner for websites that serve Quebec. It finds pages and strings that may not meet French language expectations, explains each one and points to the rule or term record behind it.

The scanner supports human review. It does not give legal advice and it never says a site is "compliant." Results are risk findings or items that need review.

This is an experimental project by Ada Lili Wang. It is a working prototype, not a product.

## Status

The crawler, all four checks, the reports (JSON, HTML and a CSV review sheet), the local scan page, saved page scanning and the scorer work end to end. On the fixture site the scanner finds every planted gap with no false positives:

| Metric | Fixture result |
| --- | --- |
| Precision | 100% (12 of 12 findings correct) |
| Recall | 100% (12 of 12 planted gaps found) |
| Needs review | 4 of 4 judgment calls sent to review |

The fixture was built alongside the scanner, so these numbers show the checks work as designed. They do not show real world accuracy. Early real site scans have already found crawl and context problems, which are listed under [Known limits](#known-limits). A labelled real site evaluation comes next.

## What it checks

| Check | What it does |
| --- | --- |
| Missing French page | An English page has no French equivalent |
| Leftover English | English strings on French pages: buttons, menus, errors, alt text |
| Metadata | English page title or meta description, missing or wrong `lang` |
| OQLF terminology | Common web anglicisms, with a Quebec French suggestion and the GDT record cited |

Everything is deterministic for now. A language model step for ambiguous terms may be tested later, once a labelled real site evaluation set exists to measure it against.

**Short strings.** Lingua alone is unreliable on interface text. It rates "Contact us" only 54% English. So short strings also use word frequency from `wordfreq`: each word leans English, leans French or is neutral. A short string counts as English when at least one word leans English and none leans French.

**Terminology.** The OQLF data lists French terms and their English equivalents, but it does not list terms to avoid. So the scanner uses a curated list of common web anglicisms in `qfscan/lexicon/web_terms.csv`. At scan time each entry is matched to its GDT record, which is cited on the finding. A term with no record is sent to review instead. Some entries are marked tolerated (for example *email*, common in Quebec usage although the OQLF recommends *courriel*) or review (for example *date d'expiration*, which depends on context, and *mail*, which can mean email or a shopping centre such as Mail Champlain).

**Crawling.** The crawler stays on one host, respects robots.txt, waits half a second between requests and stops at 50 pages (`--max-pages` to change). It asks for Quebec French first (`Accept-Language: fr-CA`) and visits French pages before English ones. English and French pages are paired by hreflang or by the language switcher link. If an English page links to a French page the crawl did not reach, it is reported as linked but not scanned, not as missing. If the start page redirects, the report says so.

**Hidden text.** English text inside elements that are hidden or meant only for screen readers is still reported, with a "Hidden on screen" or "Screen reader only" label so a reviewer knows why it may not be visible on the page.

**Blocked sites.** If a site refuses the request (for example HTTP 403), the scan stops with a clear error instead of writing an empty report. The scanner does not disguise itself as a browser.

## Repo layout

```
qfscan/
  crawl.py           crawls one site and pairs English and French pages
  text.py            extracts visible text and decides if a string is English
  terms.py           terminology check against the GDT records
  lexicon/web_terms.csv   curated list of common web anglicisms
  files.py           scans pages saved from a browser
  checks.py          runs the checks and merges repeated findings
  rules.py           why each finding matters, its reference and the fix
  report.py          builds the JSON report
  html.py            builds the HTML report and the CSV review sheet
  server.py          local web page for running scans
  score.py           scores a report against fixtures/expected.json
fixtures/
  build_fixture.py   builds the fake bilingual test site
  site/              the built site, served as a web root
  expected.json      ground truth for the 24 planted cases
scripts/
  download_oqlf_data.py   fetches the OQLF data into data/raw/
tests/
  test_fixture.py    checks the fixture against expected.json
  test_*.py          crawl, checks, terms, saved pages, CLI and server tests
data/raw/            downloaded data (not committed)
```

## Quick start

Requires Python 3.10 or later.

```bash
pip install -e ".[dev]"

# Get the OQLF data
python scripts/download_oqlf_data.py

# Serve the fixture site at http://localhost:8000
python -m http.server 8000 -d fixtures/site

# In a second terminal: scan it and score the report
python -m qfscan scan http://localhost:8000/ --out reports/fixture.json
python -m qfscan score reports/fixture.json

# Run the tests
python -m pytest
```

Each scan saves its report as `reports/<site>_<date>_<time>.json`, so earlier reports are never replaced. Use `--out` to pick a name. If that file already exists, the scanner adds `_2`, `_3` and so on, unless you pass `--overwrite`.

The scan also writes a readable HTML report (`reports/x.html`) and a review sheet (`reports/x-review.csv`) that opens in Excel. Fill in the `verdict` column with correct, wrong or unsure to measure precision on a real site. To rebuild both from an existing report, run `python -m qfscan view reports/x.json`.

**Scan from a web page.** Run `python -m qfscan serve`. Your browser opens a local page where you type a site address, click Scan and watch the progress. Reports open in a new tab and are listed on the same page. The page only runs on your own computer. Leave the terminal window open while you use it.

**Scan saved pages.** Some sites block automated tools. For those, open each page in your browser, press Ctrl+S and choose "Webpage, complete". Save the English and French versions. Then run `python -m qfscan scan-files path/to/folder`, or use the "Scan saved pages" form on the scan page. Chrome saves the page as you see it, so text added by JavaScript is checked too. The scanner reads each page's original address from the saved file, so English and French pages are still matched.

To scan a real site, pass its URL. Add `--brand "Name"` for brand or product names that should not count as English (repeat it for several). `--ignore-robots` exists only for scanning your own site. Only scan sites you are allowed to scan, and treat every result as a candidate for human review.

## Known limits

- Static HTML only. JavaScript is not run, except in pages you save from the browser.
- No OCR for images or PDFs, and no transactional emails.
- Collapsed menus are not detected as hidden.
- The terminology list is curated and small. Words with more than one meaning can be flagged wrongly. Known cases such as *mail* go to review instead, so a real anglicism like "envoyez-nous un mail" is not flagged either.
- Fixture results do not measure real world accuracy.

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
