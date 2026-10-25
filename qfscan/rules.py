"""Why each finding matters, the source behind it and how to fix it.

The scanner looks at French market fit. It does not assess legal compliance
and does not cite laws. Term findings cite OQLF language records. Coverage
findings describe what a French reader would see.
"""

COVERAGE = (
    "French coverage. A French reader would meet English here. "
    "This is a language suggestion, not a legal assessment."
)

RULES = {
    "missing_french_page": {
        "why": "This English page has no French version that the scanner could find.",
        "reference": COVERAGE,
        "fix": "Publish a French version and link the two with hreflang or a language switcher.",
    },
    "leftover_english": {
        "why": "English text on a French page.",
        "reference": COVERAGE,
        "fix": "Translate this text on the French page.",
    },
    "short_word_with_number": {
        "why": "One short word next to a number, like \"1 day\" or \"5 pm\". It may be English, but it is too short to judge alone.",
        "reference": COVERAGE,
        "fix": "Check it in its sentence. If it is English, use the French unit or word.",
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
    "france_french_term": {
        "why": "A term the OQLF labels as France usage. Quebec readers may expect the Quebec term.",
        "reference": "OQLF Grand dictionnaire terminologique. The record is linked in the evidence.",
        "fix": "Consider the Quebec term if the page is meant for Quebec readers.",
    },
    "wrong_lang_attribute": {
        "why": "The page is French but the html lang attribute says otherwise.",
        "reference": "WCAG 2.2 success criterion 3.1.1 (Language of Page). Screen readers and search engines use it.",
        "fix": "Set lang=\"fr-CA\" on the html element of French pages.",
    },
    "missing_lang_attribute": {
        "why": "The French page has no html lang attribute.",
        "reference": "WCAG 2.2 success criterion 3.1.1 (Language of Page).",
        "fix": "Set lang=\"fr-CA\" on the html element.",
    },
    "leftover_english_title": {
        "why": "The French page title is in English. Visitors see it in browser tabs and search results.",
        "reference": COVERAGE,
        "fix": "Translate the title.",
    },
    "leftover_english_metadata": {
        "why": "The French page meta description is in English. Search results may show it.",
        "reference": COVERAGE,
        "fix": "Translate the meta description.",
    },
}
