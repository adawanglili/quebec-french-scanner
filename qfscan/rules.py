"""Why each finding matters, the reference behind it and how to fix it.

References are cautious on purpose. The scanner points to a rule or a
standard. It does not say whether a site breaks the law. Where no Charter
rule applies, the text says so.
"""

CHARTER_S52 = (
    "Charter of the French Language, s. 52: catalogues, brochures, commercial "
    "directories and similar publications must be available in French. The OQLF "
    "applies this to business websites."
)

RULES = {
    "missing_french_page": {
        "why": "This English page has no French version that the scanner could find.",
        "reference": CHARTER_S52,
        "fix": "Publish a French version and link the two with hreflang or a language switcher.",
    },
    "leftover_english": {
        "why": "English text on a French page.",
        "reference": CHARTER_S52,
        "fix": "Translate this text on the French page.",
    },
    "possible_quoted_title": {
        "why": "English text in italics or a quote inside French text. It may be the title of a work.",
        "reference": "Titles of works are often kept in their original language. A person should decide.",
        "fix": "Keep it if it is a title. Add lang=\"en\" to the element so tools can tell.",
    },
    "terminology": {
        "why": "An English or France French term where Quebec French has an established term.",
        "reference": "OQLF Grand dictionnaire terminologique. The record is linked in the evidence.",
        "fix": "Use the suggested term.",
    },
    "tolerated_anglicism": {
        "why": "A borrowing that is common in Quebec usage, where the OQLF recommends a French term.",
        "reference": "OQLF Grand dictionnaire terminologique. The record is linked in the evidence.",
        "fix": "Consider the suggested term, especially in formal text.",
    },
    "terminology_review": {
        "why": "This term can be right or wrong depending on the context.",
        "reference": "OQLF Grand dictionnaire terminologique. The record is linked in the evidence.",
        "fix": "Check the meaning in context. The note explains what to look for.",
    },
    "wrong_lang_attribute": {
        "why": "The page is French but the html lang attribute says otherwise.",
        "reference": "Not a Charter rule. WCAG 2.2 success criterion 3.1.1 (Language of Page). Screen readers and search engines use it.",
        "fix": "Set lang=\"fr-CA\" on the html element of French pages.",
    },
    "missing_lang_attribute": {
        "why": "The French page has no html lang attribute.",
        "reference": "Not a Charter rule. WCAG 2.2 success criterion 3.1.1 (Language of Page).",
        "fix": "Set lang=\"fr-CA\" on the html element.",
    },
    "missing_title": {
        "why": "The French page has no title.",
        "reference": "Not a Charter rule. Browsers and search results show the title to visitors.",
        "fix": "Add a French title.",
    },
    "leftover_english_title": {
        "why": "The French page title is in English. Visitors see it in browser tabs and search results.",
        "reference": CHARTER_S52,
        "fix": "Translate the title.",
    },
    "missing_meta_description": {
        "why": "The French page has no meta description. Search engines may show other text instead.",
        "reference": "Not a Charter rule. Search results often show this text to French speakers.",
        "fix": "Add a French meta description.",
    },
    "leftover_english_metadata": {
        "why": "The French page meta description is in English. Search results may show it.",
        "reference": CHARTER_S52,
        "fix": "Translate the meta description.",
    },
}
