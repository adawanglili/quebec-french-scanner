"""Build the fictional Quartier Belvedere site into site/fr/.

Run: python experiments/llm_review/build_site.py
Edit cases.py, not the HTML, then rebuild.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from cases import PAGES

HERE = Path(__file__).resolve().parent
SITE = HERE / "site"


def render(slug: str, page: dict) -> str:
    nav = " ".join(f'<a href="/fr/{s}/">{escape(PAGES[s]["title"].split(" | ")[0])}</a>' for s in PAGES)
    body = []
    for block in page["blocks"]:
        if block[0] == "h1":
            body.append(f"<h1>{escape(block[1])}</h1>")
        elif block[0] == "p":
            body.append(f"<p>{escape(block[1])}</p>")
        else:
            body.append(f"<p>{escape(block[4])}</p>")
    return f"""<!doctype html>
<html lang="fr-CA">
<head>
<meta charset="utf-8">
<title>{escape(page["title"])}</title>
<link rel="canonical" href="https://quartier-belvedere.example/fr/{slug}/">
</head>
<body>
<nav>{nav}</nav>
<main>
{chr(10).join(body)}
</main>
</body>
</html>
"""


def main() -> None:
    for slug, page in PAGES.items():
        out = SITE / "fr" / slug / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(slug, page), encoding="utf-8")
    print(f"Built {len(PAGES)} pages in {SITE}")


if __name__ == "__main__":
    main()
