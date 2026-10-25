"""Run the LLM second pass (method 2) on a real scan report.

The scanner finds the candidates. An LLM judges each one. A person decides.

  python experiments/llm_review/review_report.py reports/site.json --provider cohere

It reads the scan report, sends each leftover English item and each terminology
item to the model with its context, and writes a review sheet next to the
report: <report>-llm.csv. The raw prompts and replies go to <report>-llm-raw.json.

Rules that keep a person in charge:
  - An LLM "ok" on alt, aria-label, title or screen reader text does not clear
    the item. It stays in review, because a French image or page can hide an
    English alt text (see Manual Tests, L12 RMHC Families).
  - An LLM "flag" or "gap" is only "likely gap, confirm". A person makes the fix.
  - Terminology items carry the OQLF record, and the model judges against it
    (prompt v3), so it cannot invent a recommendation.
  - Nothing is removed from the sheet. The LLM decision is a column, and the
    verdict column is left for you.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from providers import DEFAULT_MODELS, ask, parse_json  # noqa: E402

# Prompt v3 for terminology items. Differs from v2 (HYBRID_SYSTEM in run.py):
# each item carries the OQLF record the scanner matched, and the model must
# judge against that record instead of what it believes the OQLF says.
# Added after two invented rules: "mail" (Command A Plus) and
# "date d'expiration" (Command A on Desjardins). See Manual Tests, Test 2.
TERM_SYSTEM = """You review candidate findings from a Quebec French website scanner.
A rule based scanner matched a term that is often an anglicism or a France French usage in Quebec French.
Each item gives the term, the sentence, a suggested term, and the OQLF record the scanner matched:
  "oqlf_terms"  the terms in that record, with labels such as [Québec/Canada] or [France/Europe]
  "note"        what the scanner says to check for this term
For each item, decide from its sentence whether this occurrence is:
  "flag"   a term a Quebec French editor would replace, following OQLF recommendations
  "ok"     correct as written, for example another meaning of the word, a proper name or a brand
  "unsure" the sentence and the record do not decide it
Judge against the OQLF record given, not from memory. Do not cite any OQLF recommendation that is not in the record.
If the record lists the term as written as a correct French term for this meaning, decide "ok".
Common usage is not enough. If the record recommends another term for this meaning, decide "flag".
Reply with JSON only, in this form:
{"results": [{"id": "M01", "decision": "flag", "reason": "at most 15 words"}]}"""
PROMPT_VERSION = "v3"

ENGLISH_SYSTEM = """You review leftover English text found on the French version of a Quebec website.
A rule based scanner found each item. For each one, decide whether it is:
  "gap"    English that a French speaking user would see or hear, and that should be in French
  "ok"     correct as written, for example a brand or product name, an acronym, a proper name, or a language name in a language switcher
  "unsure" the item alone does not decide it
Text in aria-label, alt and screen reader elements counts, because screen readers read it aloud.
The scanner can be wrong about the language. If the text is already French, decide "ok".
Write the reason in English.
Reply with JSON only, in this form:
{"results": [{"id": "L01", "decision": "gap", "reason": "at most 15 words"}]}"""

ENGLISH_TYPES = {"leftover_english", "leftover_english_title", "leftover_english_metadata", "possible_quoted_title",
                 "short_word_with_number"}
TERM_TYPES = {"terminology", "terminology_review", "tolerated_anglicism", "france_french_term"}
PROTECTED = ("@alt", "@aria-label", "@title", "visuallyhidden", "sr-only", "screen-reader")


def protected(item: dict) -> bool:
    """Accessibility text: the LLM may sort it but never clears it."""
    element = (item.get("element") or "").lower()
    visibility = str(item.get("evidence", {}).get("visibility") or "").lower()
    return any(p in element for p in PROTECTED) or "screen reader" in visibility


def batches(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def judge(items: list[dict], system: str, provider: str, model: str, batch_size: int, raw: list) -> dict:
    answers = {}
    for batch in batches(items, batch_size):
        user = json.dumps({"items": [i["payload"] for i in batch]}, ensure_ascii=False)
        reply = ask(provider, model, system, user)
        raw.append({"system": system, "user": user, "text": reply.text,
                    "input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens})
        for result in parse_json(reply.text).get("results", []):
            answers[str(result.get("id"))] = (str(result.get("decision", "")).lower(), result.get("reason", ""))
    return answers


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("report", help="JSON report from python -m qfscan scan")
    parser.add_argument("--provider", default="cohere", choices=["cohere", "ollama", "anthropic", "stub"])
    parser.add_argument("--model", help="Model name. Default depends on the provider.")
    parser.add_argument("--batch-size", type=int, default=20)
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    model = args.model or DEFAULT_MODELS[args.provider]

    english, terms, rows = [], [], []
    for n, finding in enumerate(report.get("findings", []) + report.get("needs_review", []), start=1):
        evidence = finding.get("evidence") or {}
        row = {"id": f"R{n:03d}", "finding": finding}
        rows.append(row)
        if finding["type"] in ENGLISH_TYPES and finding.get("text"):
            payload = {"id": row["id"], "element": finding.get("element"), "text": finding["text"]}
            if evidence.get("context"):
                payload["context"] = evidence["context"]
            row["payload"] = payload
            english.append(row)
        elif finding["type"] in TERM_TYPES and finding.get("text"):
            payload = {"id": row["id"], "term": finding["text"],
                       "suggestion": evidence.get("suggestion") or "",
                       "sentence": evidence.get("context") or finding["text"]}
            if evidence.get("gdt_terms"):
                payload["oqlf_terms"] = evidence["gdt_terms"]
            if evidence.get("note"):
                payload["note"] = evidence["note"]
            row["payload"] = payload
            terms.append(row)

    print(f"{len(english)} leftover English items and {len(terms)} terminology items to judge with {model}.")
    raw: list = []
    answers = {}
    if english:
        answers.update(judge(english, ENGLISH_SYSTEM, args.provider, model, args.batch_size, raw))
    if terms:
        answers.update(judge(terms, TERM_SYSTEM, args.provider, model, args.batch_size, raw))

    out_csv = report_path.with_name(report_path.stem + "-llm.csv")
    counts = {}
    with out_csv.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "type", "severity", "text", "element", "occurrences", "first_page",
                         "context", "llm_decision", "llm_reason", "suggested_action", "verdict", "notes"])
        for row in rows:
            f = row["finding"]
            decision, reason = answers.get(row["id"], ("", ""))
            if "payload" not in row:
                action = "rules only"
            elif not decision:
                action = "review (no LLM answer)"
            elif decision in {"gap", "flag"}:
                action = "likely gap, confirm"
            elif decision == "ok" and protected(f):
                action = "review (accessibility text, LLM cannot clear)"
            elif decision == "ok":
                action = "likely ok, spot check"
            else:
                action = "review"
            counts[action] = counts.get(action, 0) + 1
            writer.writerow([row["id"], f["type"], f["severity"], f.get("text") or "", f.get("element"),
                             f.get("occurrences"), (f.get("pages") or [""])[0],
                             (f.get("evidence") or {}).get("context", ""), decision, reason, action, "", ""])

    out_raw = report_path.with_name(report_path.stem + "-llm-raw.json")
    out_raw.write_text(json.dumps({"provider": args.provider, "model": model,
                                   "term_prompt": PROMPT_VERSION, "calls": raw},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
    tokens_in = sum(c["input_tokens"] for c in raw)
    tokens_out = sum(c["output_tokens"] for c in raw)
    print(f"Tokens: {tokens_in} input, {tokens_out} output, {len(raw)} calls.")
    for action, count in sorted(counts.items()):
        print(f"  {action}: {count}")
    print(f"Review sheet: {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
