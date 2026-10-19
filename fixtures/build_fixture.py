#!/usr/bin/env python3
"""Build the Northwind fixture site into fixtures/site/.

The fixture is a small fake bilingual coffee shop site. It has planted
French language gaps that match the cases in fixtures/expected.json and
fixtures/README.md. Every case ID is marked in the HTML with a comment like
<!-- case: LE-01 --> so a reader can find it. The scanner must not use these
comments.

Everything that is not a planted case should be clean Quebec French, so that
any other finding counts as a false positive.

Run:
    python fixtures/build_fixture.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

SITE = Path(__file__).resolve().parent / "site"

# ---------------------------------------------------------------------------
# Page pairs. "fr" is None when the English page has no French version.
# hreflang=False means the pair is linked only by the language switcher.
# ---------------------------------------------------------------------------

PAIRS = [
    {"key": "home", "en": "/en/", "fr": "/fr/", "hreflang": True},
    {"key": "products", "en": "/en/products/", "fr": "/fr/produits/", "hreflang": True},
    {"key": "product", "en": "/en/products/house-blend/", "fr": "/fr/produits/melange-maison/", "hreflang": True},
    {"key": "checkout", "en": "/en/checkout/", "fr": "/fr/paiement/", "hreflang": True},
    {"key": "about", "en": "/en/about/", "fr": "/fr/a-propos/", "hreflang": True},  # MP-02
    {"key": "contact", "en": "/en/contact/", "fr": "/fr/contact/", "hreflang": True},
    {"key": "privacy", "en": "/en/privacy/", "fr": "/fr/confidentialite/", "hreflang": True},
    {"key": "terms", "en": "/en/terms/", "fr": "/fr/conditions/", "hreflang": True},
    {"key": "blog", "en": "/en/blog/launch/", "fr": "/fr/blogue/lancement/", "hreflang": False},  # MP-03
    {"key": "careers", "en": "/en/careers/", "fr": None, "hreflang": False},  # MP-01
]
BY_KEY = {p["key"]: p for p in PAIRS}

CSS = """
:root { --ink: #2b2118; --paper: #faf6f0; --accent: #8a4b2a; --line: #e2d8cc; }
* { box-sizing: border-box; }
body { margin: 0; font: 16px/1.55 Georgia, "Times New Roman", serif; color: var(--ink); background: var(--paper); }
header, main, footer { max-width: 860px; margin: 0 auto; padding: 16px; }
header { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 24px; border-bottom: 1px solid var(--line); }
.logo { font-weight: bold; font-size: 1.3rem; color: var(--accent); text-decoration: none; }
nav ul { list-style: none; display: flex; flex-wrap: wrap; gap: 16px; margin: 0; padding: 0; }
nav a, .lang-switch { color: var(--ink); }
.lang-switch { margin-left: auto; }
img { max-width: 100%; height: auto; display: block; background: var(--line); }
.products { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; padding: 0; list-style: none; }
.products li { border: 1px solid var(--line); padding: 12px; background: #fff; }
form { display: grid; gap: 12px; max-width: 420px; }
label { display: grid; gap: 4px; }
input, textarea, button { font: inherit; padding: 8px; }
button { background: var(--accent); color: #fff; border: 0; cursor: pointer; }
.field-error { color: #a12020; font-size: 0.9rem; }
footer { border-top: 1px solid var(--line); font-size: 0.9rem; }
footer ul { list-style: none; display: flex; gap: 16px; padding: 0; }
""".strip()

PLACEHOLDER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="800" height="420" viewBox="0 0 800 420">
<rect width="800" height="420" fill="#e2d8cc"/>
<circle cx="400" cy="210" r="90" fill="#8a4b2a"/>
<rect x="470" y="180" width="40" height="60" rx="20" fill="none" stroke="#8a4b2a" stroke-width="14"/>
</svg>
"""

# ---------------------------------------------------------------------------
# Shared layout
# ---------------------------------------------------------------------------

NAV = {
    "en": [
        ("home", "Home"),
        ("products", "Our coffees"),
        ("about", "About"),
        ("blog", "Blog"),
        ("careers", "Careers"),
        ("contact", "Contact us"),
        ("checkout", "Cart"),
    ],
    "fr": [
        ("home", "Accueil"),
        ("products", "Nos cafés"),
        ("about", "À propos"),
        ("blog", "Blogue"),
        # LE-02: English menu item in the shared French nav.
        ("contact", "Contact us<!-- case: LE-02 -->"),
        ("checkout", "Panier"),
    ],
}

FOOTER = {
    "en": """
<ul>
  <li><a href="/en/privacy/">Privacy policy</a></li>
  <li><a href="/en/terms/">Terms of use</a></li>
</ul>
<p>Northwind Coffee Roasters is a registered trademark. Prices and availability are subject to change without notice. All rights reserved.</p>
""",
    "fr": """
<ul>
  <li><a href="/fr/confidentialite/">Politique de confidentialité</a></li>
  <li><a href="/fr/conditions/">Conditions d'utilisation</a></li>
</ul>
<!-- case: LE-05 -->
<p>Northwind Coffee Roasters is a registered trademark. Prices and availability are subject to change without notice. All rights reserved.</p>
""",
}

LANG_ATTR = {"en": "en-CA", "fr": "fr-CA"}


def head_links(pair: dict, lang: str) -> str:
    """hreflang alternates for a page, or nothing when the pair has none."""
    if not pair["hreflang"] or not pair["fr"]:
        return ""
    return (
        f'<link rel="alternate" hreflang="en-CA" href="{pair["en"]}">\n'
        f'<link rel="alternate" hreflang="fr-CA" href="{pair["fr"]}">\n'
        f'<link rel="alternate" hreflang="x-default" href="{pair["fr"]}">\n'
    )


def switcher(pair: dict, lang: str) -> str:
    if lang == "fr":
        return f'<a class="lang-switch" href="{pair["en"]}" lang="en" hreflang="en-CA">English</a>'
    if pair["fr"]:
        return f'<a class="lang-switch" href="{pair["fr"]}" lang="fr" hreflang="fr-CA">Français</a>'
    return ""  # MP-01: no French page, so no switcher link.


def render(pair: dict, lang: str, page: dict) -> str:
    html_lang = page.get("html_lang", LANG_ATTR[lang])
    description = page.get("description")
    meta = f'<meta name="description" content="{description}">\n' if description is not None else ""
    nav_items = "\n".join(
        f'    <li><a href="{BY_KEY[key][lang]}">{label}</a></li>' for key, label in NAV[lang]
    )
    home = BY_KEY["home"][lang]
    return f"""<!doctype html>
<html lang="{html_lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{page["title"]}</title>
{meta}{head_links(pair, lang)}<link rel="stylesheet" href="/assets/style.css">
{page.get("head_comment", "")}</head>
<body>
<header>
  <a class="logo" href="{home}">Northwind</a>
  <nav>
  <ul>
{nav_items}
  </ul>
  </nav>
  {switcher(pair, lang)}
</header>
<main>
{page["body"].strip()}
</main>
<footer>
{FOOTER[lang].strip()}
</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Page content
# ---------------------------------------------------------------------------

PAGES: dict[str, dict[str, dict]] = {}

PAGES["home"] = {
    "en": {
        "title": "Northwind | Small batch coffee roasted in Montréal",
        "description": "Northwind roasts small batch coffee in Montréal. Shop our beans online or visit the café.",
        "body": """
<h1>Coffee roasted in Montréal, one small batch at a time</h1>
<img src="/assets/coffee.svg" alt="Woman holding a coffee cup" width="800" height="420">
<p>We buy green coffee directly from growers and roast it every Tuesday in our café on Saint-Denis Street.</p>
<h2>Opening hours</h2>
<p>Monday to Friday, 7 a.m. to 6 p.m. Open on weekends from 9 a.m. to 5 p.m.</p>
<p><a href="/en/products/">See our coffees</a></p>
""",
    },
    "fr": {
        "title": "Northwind | Café torréfié en petits lots à Montréal",
        "description": "Northwind torréfie du café en petits lots à Montréal. Achetez nos grains en ligne ou visitez le café.",
        "body": """
<h1>Du café torréfié à Montréal, un petit lot à la fois</h1>
<!-- case: LE-04 -->
<img src="/assets/coffee.svg" alt="Woman holding a coffee cup" width="800" height="420">
<p>Nous achetons le café vert directement aux producteurs et nous le torréfions chaque mardi dans notre café de la rue Saint-Denis.</p>
<h2>Heures d'ouverture</h2>
<!-- case: TM-04 -->
<p>Du lundi au vendredi, de 7 h à 18 h. Ouvert le week-end de 9 h à 17 h.</p>
<p><a href="/fr/produits/">Découvrir nos cafés</a></p>
""",
    },
}

PAGES["products"] = {
    "en": {
        "title": "Our coffees | Northwind",
        "description": "Whole bean and ground coffee roasted each week in Montréal.",
        "body": """
<h1>Our coffees</h1>
<ul class="products">
  <li><h2><a href="/en/products/house-blend/">House blend</a></h2><p>Chocolate, hazelnut, a round finish.</p><p>$18.95 for 340 g</p></li>
  <li><h2>Northern dark roast</h2><p>Dark caramel, low acidity.</p><p>$19.95 for 340 g</p></li>
  <li><h2>Decaf from Colombia</h2><p>Brown sugar, red apple.</p><p>$18.95 for 340 g</p></li>
</ul>
""",
    },
    "fr": {
        # MD-02: English title on a French page.
        "head_comment": "<!-- case: MD-02 -->\n",
        "title": "Our coffees | Northwind",
        "description": "Café en grains et café moulu torréfiés chaque semaine à Montréal.",
        "body": """
<h1>Nos cafés</h1>
<ul class="products">
  <li><h2><a href="/fr/produits/melange-maison/">Mélange maison</a></h2><p>Chocolat, noisette, finale ronde.</p><p>18,95 $ les 340 g</p></li>
  <li><h2>Nordique foncé</h2><p>Caramel foncé, faible acidité.</p><p>19,95 $ les 340 g</p></li>
  <li><h2>Décaféiné de Colombie</h2><p>Cassonade, pomme rouge.</p><p>18,95 $ les 340 g</p></li>
</ul>
""",
    },
}

PAGES["product"] = {
    "en": {
        "title": "House blend | Northwind",
        "description": "Our house blend has notes of chocolate and hazelnut. Roasted every week in Montréal.",
        "body": """
<h1>House blend</h1>
<img src="/assets/coffee.svg" alt="Bag of house blend coffee beans" width="800" height="420">
<p>A medium roast with notes of chocolate and hazelnut. It works well in a drip machine or a French press.</p>
<p>Product code: SKU-4471</p>
<p>$18.95 for 340 g</p>
<form action="/en/checkout/" method="get">
  <label>Quantity <input type="number" name="qty" value="1" min="1"></label>
  <button type="submit">Add to cart</button>
</form>
<p><button type="button">Download the brewing guide</button></p>
""",
    },
    "fr": {
        "title": "Mélange maison | Northwind",
        "description": "Notre mélange maison offre des notes de chocolat et de noisette. Torréfié chaque semaine à Montréal.",
        "body": """
<h1>Mélange maison</h1>
<img src="/assets/coffee.svg" alt="Sac de grains de café mélange maison" width="800" height="420">
<p>Une torréfaction moyenne aux notes de chocolat et de noisette. Il convient à la cafetière filtre comme à la cafetière à piston.</p>
<!-- case: LE-08 -->
<p>Code de produit : SKU-4471</p>
<p>18,95 $ les 340 g</p>
<form action="/fr/paiement/" method="get">
  <label>Quantité <input type="number" name="qty" value="1" min="1"></label>
  <!-- case: LE-01 -->
  <button type="submit">Add to cart</button>
</form>
<!-- case: TM-06 -->
<p><button type="button">Télécharger le guide d'infusion</button></p>
""",
    },
}

PAGES["checkout"] = {
    "en": {
        "title": "Cart and payment | Northwind",
        "description": "Review your shopping cart and pay securely.",
        "body": """
<h1>Your shopping cart</h1>
<p>House blend, 340 g, quantity 1: $18.95</p>
<h2>Payment</h2>
<form action="#" method="post">
  <label>Name on card <input type="text" name="name" autocomplete="cc-name"></label>
  <label>Card number <input type="text" name="card" inputmode="numeric" autocomplete="cc-number"></label>
  <label>Expiry date <input type="text" name="exp" placeholder="MM/YY" autocomplete="cc-exp"></label>
  <label>Security code <input type="text" name="cvc" inputmode="numeric" autocomplete="cc-csc"></label>
  <button type="submit">Pay now</button>
</form>
""",
    },
    "fr": {
        "title": "Panier et paiement | Northwind",
        "description": "Vérifiez votre panier d'achat et payez en toute sécurité.",
        "body": """
<!-- case: TM-01 -->
<h1>Votre panier d'achat</h1>
<p>Mélange maison, 340 g, quantité 1 : 18,95 $</p>
<h2>Paiement</h2>
<form action="#" method="post">
  <label>Nom sur la carte <input type="text" name="name" autocomplete="cc-name"></label>
  <label>Numéro de carte <input type="text" name="card" inputmode="numeric" autocomplete="cc-number"></label>
  <!-- case: TM-07 -->
  <label>Date d'expiration <input type="text" name="exp" placeholder="MM/AA" autocomplete="cc-exp"></label>
  <label>Code de sécurité <input type="text" name="cvc" inputmode="numeric" autocomplete="cc-csc"></label>
  <button type="submit">Payer maintenant</button>
</form>
""",
    },
}

PAGES["about"] = {
    "en": {
        "title": "About us | Northwind",
        "description": "Northwind is a small coffee roaster founded in Montréal in 2019.",
        "body": """
<h1>About us</h1>
<p>Northwind started in 2019 as a small roaster in the back of a bakery. Today we have a café, a team of eight and customers across Quebec.</p>
<p>We work with the same growers year after year and pay above the market price.</p>
""",
    },
    "fr": {
        # MD-05: correct lang, French title and description. MP-02: hreflang pair.
        "head_comment": "<!-- case: MD-05 -->\n<!-- case: MP-02 -->\n",
        "title": "À propos | Northwind",
        "description": "Northwind est une petite brûlerie fondée à Montréal en 2019.",
        "body": """
<h1>À propos</h1>
<p>Northwind a commencé en 2019 comme petite brûlerie à l'arrière d'une boulangerie. Aujourd'hui, nous avons un café, une équipe de huit personnes et des clients partout au Québec.</p>
<p>Nous travaillons avec les mêmes producteurs d'année en année et nous les payons au-dessus du prix du marché.</p>
""",
    },
}

PAGES["contact"] = {
    "en": {
        "title": "Contact us | Northwind",
        "description": "Visit the Northwind café on Saint-Denis Street or write to us.",
        "body": """
<h1>Contact us</h1>
<p>Write to us by email at bonjour@northwind.example or use the form below.</p>
<form action="#" method="post" novalidate>
  <label>Name <input type="text" name="name" required></label>
  <span class="field-error" hidden>This field is required</span>
  <label>Email address <input type="email" name="email" required></label>
  <span class="field-error" hidden>Please enter a valid email address</span>
  <label>Message <textarea name="message" rows="4"></textarea></label>
  <button type="submit">Send</button>
</form>
<h2>Getting here</h2>
<p>1200 Saint-Denis Street, Montréal, Quebec. Free parking behind the building. Berri-UQAM metro station is a five minute walk.</p>
""",
    },
    "fr": {
        "title": "Nous joindre | Northwind",
        "description": "Visitez le café Northwind sur la rue Saint-Denis ou écrivez-nous.",
        "body": """
<h1>Nous joindre</h1>
<!-- case: LE-07 -->
<p>Écrivez-nous par email à bonjour@northwind.example ou utilisez le formulaire ci-dessous.</p>
<form action="#" method="post" novalidate>
  <label>Nom <input type="text" name="name" required></label>
  <!-- case: LE-03 -->
  <span class="field-error" hidden>This field is required</span>
  <label>Adresse courriel <input type="email" name="email" required></label>
  <span class="field-error" hidden>Veuillez entrer une adresse courriel valide.</span>
  <label>Message <textarea name="message" rows="4"></textarea></label>
  <button type="submit">Envoyer</button>
</form>
<h2>Pour nous trouver</h2>
<!-- case: TM-03 -->
<p>1200, rue Saint-Denis, Montréal (Québec). Parking gratuit derrière l'immeuble. La station de métro Berri-UQAM est à cinq minutes de marche.</p>
""",
    },
}

PAGES["privacy"] = {
    "en": {
        "title": "Privacy policy | Northwind",
        "description": "How Northwind collects, uses and protects your personal information.",
        "body": """
<h1>Privacy policy</h1>
<p>We collect your name, address and email address when you place an order. We use them only to process the order and to contact you about it.</p>
<p>If you agree, we may send you an email when a new coffee arrives. You can unsubscribe at any time.</p>
<p>Our site uses cookies to keep your shopping cart. You can refuse them in your browser settings.</p>
<p>To access or correct your personal information, write to our privacy officer at vieprivee@northwind.example.</p>
""",
    },
    "fr": {
        # MD-03: no meta description on this French page.
        "head_comment": "<!-- case: MD-03 -->\n",
        "title": "Politique de confidentialité | Northwind",
        "description": None,
        "body": """
<h1>Politique de confidentialité</h1>
<p>Nous recueillons votre nom, votre adresse et votre adresse courriel lorsque vous passez une commande. Nous les utilisons seulement pour traiter la commande et pour communiquer avec vous à son sujet.</p>
<!-- case: TM-02 -->
<p>Si vous y consentez, nous pouvons vous envoyer un mail lorsqu'un nouveau café arrive. Vous pouvez vous désabonner en tout temps.</p>
<p>Notre site utilise des témoins de connexion pour conserver votre panier. Vous pouvez les refuser dans les paramètres de votre navigateur.</p>
<p>Pour consulter ou corriger vos renseignements personnels, écrivez à notre responsable de la protection des renseignements personnels à vieprivee@northwind.example.</p>
""",
    },
}

PAGES["terms"] = {
    "en": {
        "title": "Terms of use | Northwind",
        "description": "The terms that apply when you use the Northwind site and buy our coffee.",
        "body": """
<h1>Terms of use</h1>
<p>By using this site, you accept these terms. Prices are in Canadian dollars and include applicable taxes when stated.</p>
<p>You can return an unopened bag within 30 days of delivery for a full refund.</p>
<p>These terms are governed by the laws in force in Quebec.</p>
""",
    },
    "fr": {
        # MD-01: wrong lang attribute on a French page.
        "html_lang": "en",
        "head_comment": "<!-- case: MD-01 -->\n",
        "title": "Conditions d'utilisation | Northwind",
        "description": "Les conditions qui s'appliquent lorsque vous utilisez le site Northwind et achetez notre café.",
        "body": """
<h1>Conditions d'utilisation</h1>
<p>En utilisant ce site, vous acceptez les présentes conditions. Les prix sont en dollars canadiens et incluent les taxes applicables lorsque c'est indiqué.</p>
<p>Vous pouvez retourner un sac non ouvert dans les 30 jours suivant la livraison pour obtenir un remboursement complet.</p>
<p>Les présentes conditions sont régies par les lois en vigueur au Québec.</p>
""",
    },
}

PAGES["blog"] = {
    "en": {
        "title": "We are launching our online store | Northwind",
        "description": "Our coffee is now available online, with delivery across Quebec.",
        "body": """
<article>
<h1>We are launching our online store</h1>
<p>Starting today, you can order our coffee online and get it delivered anywhere in Quebec.</p>
<p>No need to go shopping downtown on a Saturday. Your coffee comes to you.</p>
<p>While we built the store, the team kept rereading <em>The Slow Morning Brew</em>, a small book about taking time over the first cup of the day.</p>
</article>
""",
    },
    "fr": {
        # MD-04: English meta description. MP-03: no hreflang, switcher only.
        "head_comment": "<!-- case: MD-04 -->\n<!-- case: MP-03 -->\n",
        "title": "Nous lançons notre boutique en ligne | Northwind",
        "description": "Our coffee is now available online, with delivery across Quebec.",
        "body": """
<article>
<h1>Nous lançons notre boutique en ligne</h1>
<p>Dès aujourd'hui, vous pouvez commander notre café en ligne et le faire livrer partout au Québec.</p>
<!-- case: TM-05 -->
<p>Plus besoin d'aller faire du shopping au centre-ville un samedi. Votre café vient à vous.</p>
<!-- case: LE-09 -->
<p>Pendant la création de la boutique, l'équipe relisait sans cesse <em>The Slow Morning Brew</em>, un petit livre sur l'art de prendre son temps devant la première tasse de la journée.</p>
</article>
""",
    },
}

PAGES["careers"] = {
    "en": {
        # MP-01: English only.
        "head_comment": "<!-- case: MP-01 -->\n",
        "title": "Careers | Northwind",
        "description": "Join the Northwind team in Montréal.",
        "body": """
<h1>Careers</h1>
<p>We are hiring a part time barista for weekend shifts at our Saint-Denis café.</p>
<p>Send your resume to emplois@northwind.example.</p>
""",
    },
}


def output_path(url_path: str) -> Path:
    return SITE / url_path.strip("/") / "index.html"


def build() -> list[Path]:
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "assets").mkdir(parents=True)
    (SITE / "assets" / "style.css").write_text(CSS + "\n", encoding="utf-8")
    (SITE / "assets" / "coffee.svg").write_text(PLACEHOLDER_SVG, encoding="utf-8")

    written = []
    for pair in PAIRS:
        for lang in ("en", "fr"):
            if not pair[lang]:
                continue
            target = output_path(pair[lang])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(render(pair, lang, PAGES[pair["key"]][lang]), encoding="utf-8")
            written.append(target)

    # Root page: a plain language chooser that links into both trees.
    (SITE / "index.html").write_text(
        """<!doctype html>
<html lang="fr-CA">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Northwind | Café torréfié à Montréal</title>
<meta name="description" content="Choisissez votre langue pour visiter le site de Northwind.">
<link rel="stylesheet" href="/assets/style.css">
</head>
<body>
<main>
<h1>Northwind</h1>
<p><a href="/fr/">Français</a></p>
<p><a href="/en/" lang="en" hreflang="en-CA">English</a></p>
</main>
</body>
</html>
""",
        encoding="utf-8",
    )
    written.append(SITE / "index.html")
    return written


if __name__ == "__main__":
    files = build()
    print(f"Built {len(files)} pages into {SITE}")
