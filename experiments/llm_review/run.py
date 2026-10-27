"""Compare three ways to judge middle ground terms on the Quartier Belvedere site.

  nlp     rules only. Every match of a middle ground term is treated as a flag.
  hybrid  rules first, then an LLM judges each match from its sentence.
  llm     an LLM reads the full text of each page and lists the terms itself.

Run from the repo root:
  python experiments/llm_review/build_site.py
  python experiments/llm_review/run.py --provider cohere

Results go to experiments/llm_review/results/. Raw replies are saved, so a
second run with the same settings costs nothing. Use --fresh to call the
model again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from cases import PAGES, cases  # noqa: E402
from providers import DEFAULT_MODELS, ask, parse_json  # noqa: E402
from qfscan.terms import find_terms, load_lexicon  # noqa: E402
from qfscan.text import extract_units  # noqa: E402

SITE = HERE / "site"
RESULTS = HERE / "results"
LEXICON = HERE / "lexicon.csv"
NO_DATA = HERE / "no-data"  # keeps the run independent of the OQLF download

HYBRID_SYSTEM = """You review candidate findings from a Quebec French website scanner.
A rule based scanner matched a word that is often an anglicism in Quebec French.
For each item, decide from its sentence whether this occurrence is:
  "flag"   an anglicism that a Quebec French editor would replace, following OQLF recommendations
  "ok"     correct as written, for example another meaning of the word, a proper name or a brand
  "unsure" the sentence truly does not decide it
Common usage is not enough. If the OQLF recommends another term for this meaning, decide "flag".
Reply with JSON only, in this form:
{"results": [{"id": "M01", "decision": "flag", "reason": "at most 15 words"}]}"""

LLM_ONLY_SYSTEM = """You review the French text of one page from a website that serves Quebec.
List every word or expression that a Quebec French editor would replace because it is an
anglicism or a France French usage, following OQLF recommendations.
Do not report proper names, brands or words used in another, correct meaning.
Reply with JSON only, in this form:
{"findings": [{"term": "the word as written", "quote": "the full sentence that contains it", "suggestion": "Quebec French term"}]}
If there is nothing to report, reply {"findings": []}."""

from review_report import TERM_SYSTEM as HYBRID_SYSTEM_V3  # noqa: E402  (prompt v3)

# OQLF records for each meaning of the four terms, from the GDT (fiches signees,
# 2026-01-19). Prompt v3 sends them with each item, so the model judges against
# the record and not against what it believes the OQLF says. "mail" has two
# meanings and two records: the email one and the shopping mall one.
RECORDS = {
    "mail": "email: courriel (n. m.);courrier électronique (n. m.);message électronique (n. m.) | "
            "shopping mall: galerie marchande (n. f.);galerie commerciale (n. f.);galerie de boutiques (n. f.);"
            "mail commercial (n. m.);mail (n. m.)",
    "chat": "online chat: clavardage (n. m.) [Québec/Canada];cyberbavardage (n. m.) [Québec/Canada];"
            "bavardage-clavier (n. m.) [Québec/Canada];dialogue en ligne (n. m.)",
    "booking": "booking, reservation: réservation (n. f.)",
    "spam": "junk email: pourriel (n. m.)",
}

PROMPTS = {"v2": HYBRID_SYSTEM, "v3": HYBRID_SYSTEM_V3}


def prompt_version(name: str) -> str:
    digest = hashlib.sha256((PROMPTS[name] + LLM_ONLY_SYSTEM).encode()).hexdigest()[:10]
    return digest if name == "v2" else f"{name}-{digest}"


PROMPT_VERSION = prompt_version("v2")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("’", "'")).strip().lower()


def page_units(slug: str):
    html = (SITE / "fr" / slug / "index.html").read_text(encoding="utf-8")
    return [u for u in extract_units(html) if u.kind == "text"]


def find_case(slug: str, text: str, term: str, all_cases: list[dict]) -> dict | None:
    for case in all_cases:
        if case["page"] == slug and norm(case["text"]) == norm(text) and case["term"] in term.lower():
            return case
    return None


def base_term(form: str) -> str:
    form = form.lower()
    return next((t for t in RECORDS if form.startswith(t)), form)


def nlp_matches(all_cases: list[dict]) -> list[dict]:
    """Every match of a middle ground term, in page order."""
    lexicon = load_lexicon(LEXICON, NO_DATA)
    items = []
    for slug, page in PAGES.items():
        for unit in page_units(slug):
            for match in find_terms(unit.text, lexicon):
                case = find_case(slug, unit.text, match.form, all_cases)
                items.append({
                    "id": f"M{len(items) + 1:02d}",
                    "page": slug,
                    "page_title": page["title"],
                    "element": unit.element,
                    "term": match.form,
                    "suggestion": match.entry.suggestion,
                    "oqlf_terms": RECORDS.get(base_term(match.form), ""),
                    "note": match.entry.note or "",
                    "sentence": unit.text,
                    "case": case["id"] if case else None,
                })
    return items


# ---------- arms ----------

def arm_nlp(all_cases, items):
    decisions = {i["case"]: "flag" for i in items if i["case"]}
    extras = [i for i in items if not i["case"]]
    return decisions, extras, {"input_tokens": 0, "output_tokens": 0, "calls": 0, "seconds": 0.0}


def cached_ask(provider, model, system, user, cache: Path, fresh: bool):
    if cache.exists() and not fresh:
        return json.loads(cache.read_text(encoding="utf-8"))
    reply = ask(provider, model, system, user)
    record = {"system": system, "user": user, "text": reply.text, "input_tokens": reply.input_tokens,
              "output_tokens": reply.output_tokens, "seconds": reply.seconds}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def arm_hybrid(all_cases, items, provider, model, run, raw_dir, fresh, batch_size, prompt="v2"):
    usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "seconds": 0.0}
    answers = {}
    for start in range(0, len(items), batch_size):
        batch = items[start:start + batch_size]
        keys = ("id", "term", "suggestion", "sentence") + (("oqlf_terms", "note") if prompt == "v3" else ())
        payload = {"items": [{k: i[k] for k in keys} for i in batch]}
        user = json.dumps(payload, ensure_ascii=False)
        record = cached_ask(provider, model, PROMPTS[prompt], user,
                            raw_dir / f"hybrid-run{run}-batch{start // batch_size + 1}.json", fresh)
        for key in ("input_tokens", "output_tokens", "seconds"):
            usage[key] += record[key]
        usage["calls"] += 1
        for result in parse_json(record["text"]).get("results", []):
            answers[str(result.get("id"))] = (str(result.get("decision", "unsure")).lower(), result.get("reason", ""))
    decisions, extras, reasons = {}, [], {}
    for item in items:
        decision, reason = answers.get(item["id"], ("unsure", "no answer"))
        if decision not in {"flag", "ok", "unsure"}:
            decision = "unsure"
        if item["case"]:
            decisions[item["case"]] = decision
            reasons[item["case"]] = reason
        elif decision == "flag":
            extras.append(item)
    return decisions, extras, usage, reasons


def map_llm_finding(slug, finding, all_cases):
    quote, term = norm(finding.get("quote", "")), norm(finding.get("term", ""))
    best, best_score = None, 0.0
    for case in all_cases:
        if case["page"] != slug or case["term"] not in term:
            continue
        text = norm(case["text"])
        score = 1.0 if (quote and (quote in text or text in quote)) else SequenceMatcher(None, quote, text).ratio()
        if score > best_score:
            best, best_score = case, score
    return best if best_score >= 0.6 else None


def arm_llm(all_cases, provider, model, run, raw_dir, fresh):
    usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "seconds": 0.0}
    decisions = {c["id"]: "ok" for c in all_cases}
    extras = []
    for slug in PAGES:
        user = "\n".join(u.text for u in page_units(slug))
        record = cached_ask(provider, model, LLM_ONLY_SYSTEM, user, raw_dir / f"llm-run{run}-{slug}.json", fresh)
        for key in ("input_tokens", "output_tokens", "seconds"):
            usage[key] += record[key]
        usage["calls"] += 1
        for finding in parse_json(record["text"]).get("findings", []):
            case = map_llm_finding(slug, finding, all_cases)
            if case:
                decisions[case["id"]] = "flag"
            else:
                extras.append({"page": slug, **finding})
    return decisions, extras, usage


# ---------- scoring ----------

def score(all_cases, decisions, extras):
    out = {"cases": len(all_cases), "correct": 0, "false_flags": 0, "missed": 0, "unsure": 0,
           "extra_findings": len(extras), "wrong_cases": []}
    for case in all_cases:
        decision = decisions.get(case["id"], "ok")
        if decision == "unsure":
            out["unsure"] += 1
        elif decision == case["label"]:
            out["correct"] += 1
        else:
            out["false_flags" if decision == "flag" else "missed"] += 1
            out["wrong_cases"].append(case["id"])
    out["errors"] = out["false_flags"] + out["missed"] + out["extra_findings"]
    out["error_rate"] = out["errors"] / (out["cases"] + out["extra_findings"])
    out["left_for_review"] = out["unsure"]
    return out


def mean(runs, key):
    return statistics.mean(r[key] for r in runs)


def pct(x):
    return f"{x * 100:.0f}%"


def write_summary(all_cases, items, results, provider, model, out_dir: Path):
    rows = []
    for arm in ("nlp", "hybrid", "llm"):
        if arm not in results:
            continue
        runs = results[arm]
        rows.append({
            "arm": arm,
            "runs": len(runs),
            "errors": mean(runs, "errors"),
            "error_rate": mean(runs, "error_rate"),
            "false_flags": mean(runs, "false_flags"),
            "missed": mean(runs, "missed"),
            "extra_findings": mean(runs, "extra_findings"),
            "left_for_review": mean(runs, "left_for_review"),
            "calls": mean(runs, "calls"),
            "input_tokens": mean(runs, "input_tokens"),
            "output_tokens": mean(runs, "output_tokens"),
            "total_tokens": mean(runs, "input_tokens") + mean(runs, "output_tokens"),
            "error_range": (min(r["errors"] for r in runs), max(r["errors"] for r in runs)),
        })
    by_arm = {r["arm"]: r for r in rows}
    labels = {"nlp": "Rules alone", "hybrid": "Rules + LLM second pass", "llm": "LLM only (full pages)"}

    lines = [
        "# LLM second pass experiment",
        "",
        f"Run on {datetime.now():%Y-%m-%d %H:%M}. Provider `{provider}`, model `{model}`, prompt version `{PROMPT_VERSION}`.",
        f"{len(all_cases)} planted cases on {len(PAGES)} pages: "
        f"{sum(c['label'] == 'flag' for c in all_cases)} anglicisms and {sum(c['label'] == 'ok' for c in all_cases)} correct uses. "
        f"The rules matched {len(items)} occurrences.",
        "",
        "| Arm | Runs | Errors | Error rate | False flags | Missed | Extra findings | Left for review | Calls | Input tokens | Output tokens | Total tokens |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        lo, hi = r["error_range"]
        spread = f" ({lo} to {hi})" if lo != hi else ""
        lines.append(
            f"| {labels[r['arm']]} | {r['runs']} | {r['errors']:.1f}{spread} | {pct(r['error_rate'])} | {r['false_flags']:.1f} | "
            f"{r['missed']:.1f} | {r['extra_findings']:.1f} | {r['left_for_review']:.1f} | {r['calls']:.0f} | "
            f"{r['input_tokens']:.0f} | {r['output_tokens']:.0f} | {r['total_tokens']:.0f} |")
    lines.append("")
    if "nlp" in by_arm and "hybrid" in by_arm and by_arm["nlp"]["errors"]:
        cut = 1 - by_arm["hybrid"]["errors"] / by_arm["nlp"]["errors"]
        lines.append(f"The second pass cut errors by {pct(cut)} compared with rules alone.")
    if "hybrid" in by_arm and "llm" in by_arm and by_arm["llm"]["total_tokens"]:
        share = by_arm["hybrid"]["total_tokens"] / by_arm["llm"]["total_tokens"]
        lines.append(f"It used {pct(share)} of the tokens of the full page LLM scan.")
    if "hybrid" in by_arm and "llm" in by_arm:
        lines.append(f"Errors: second pass {by_arm['hybrid']['errors']:.1f}, full page LLM {by_arm['llm']['errors']:.1f}.")
    page_chars = sum(len(u.text) for slug in PAGES for u in page_units(slug))
    if "hybrid" in by_arm and items:
        lines.append(f"Second pass cost: about {by_arm['hybrid']['total_tokens'] / len(items):.0f} tokens per flagged item "
                     "(the instructions are shared across a batch, so larger batches cost less per item).")
    if "llm" in by_arm and page_chars:
        lines.append(f"Full page cost: about {by_arm['llm']['total_tokens'] / page_chars * 1000:.0f} tokens per 1,000 characters "
                     f"of page text ({page_chars:,} characters here). Real pages are often 5,000 to 20,000 characters, "
                     "so use these two rates to estimate a real site.")
    lines += [
        "",
        "How to read this:",
        "",
        "- Errors are false flags plus missed anglicisms plus extra findings on text that is meant to be clean.",
        "- The rules treat every match as a flag, so their errors are the correct uses they cannot tell apart.",
        "- \"Left for review\" is what the LLM marked unsure. It is not counted as an error, but a person still has to check it.",
        "- Half the cases are deliberately ambiguous. Real sites have far fewer, so the error rates here are not real world rates.",
        "- The cases were written by the same person who wrote the prompts. Treat this as a pilot, not a benchmark.",
        "",
    ]
    wrong = {arm: sorted({cid for run in runs for cid in run["wrong_cases"]}) for arm, runs in results.items()}
    for arm, ids in wrong.items():
        if ids:
            lines.append(f"Cases wrong at least once with {labels[arm]}: {', '.join(ids)}")
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps({"provider": provider, "model": model,
                                                      "prompt_version": PROMPT_VERSION, "arms": rows,
                                                      "runs": results}, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", default="cohere", choices=["cohere", "ollama", "anthropic", "stub"])
    parser.add_argument("--model", help="Model name. Default depends on the provider.")
    parser.add_argument("--runs", type=int, default=3, help="Runs per LLM arm, to see how stable the answers are")
    parser.add_argument("--arms", default="nlp,hybrid,llm")
    parser.add_argument("--batch-size", type=int, default=30, help="Items per second pass call")
    parser.add_argument("--fresh", action="store_true", help="Call the model again instead of reusing saved replies")
    parser.add_argument("--out", help="Results folder. Default: results/<provider>-<model>[-v3]")
    parser.add_argument("--prompt", default="v2", choices=sorted(PROMPTS),
                        help="Second pass prompt. v3 sends the OQLF records with each item.")
    args = parser.parse_args(argv)

    if not (SITE / "fr").exists():
        raise SystemExit("Build the site first: python experiments/llm_review/build_site.py")
    model = args.model or DEFAULT_MODELS[args.provider]
    safe_model = re.sub(r"[^\w.-]+", "_", model)
    suffix = "" if args.prompt == "v2" else f"-{args.prompt}"
    out_dir = Path(args.out) if args.out else RESULTS / f"{args.provider}-{safe_model}{suffix}"
    global PROMPT_VERSION
    PROMPT_VERSION = prompt_version(args.prompt)
    raw_dir = out_dir / "raw"
    arms = [a.strip() for a in args.arms.split(",")]

    all_cases = cases()
    items = nlp_matches(all_cases)
    unmatched = [c["id"] for c in all_cases if c["id"] not in {i["case"] for i in items}]
    if unmatched:
        print(f"Warning: the rules did not match cases {', '.join(unmatched)}")

    results = {}
    if "nlp" in arms:
        decisions, extras, usage = arm_nlp(all_cases, items)
        results["nlp"] = [{**score(all_cases, decisions, extras), **usage}]
    for run in range(1, args.runs + 1):
        if "hybrid" in arms:
            print(f"Second pass, run {run}")
            decisions, extras, usage, reasons = arm_hybrid(all_cases, items, args.provider, model, run, raw_dir,
                                                           args.fresh, args.batch_size, args.prompt)
            results.setdefault("hybrid", []).append({**score(all_cases, decisions, extras), **usage,
                                                     "decisions": decisions, "reasons": reasons})
        if "llm" in arms:
            print(f"Full page LLM, run {run}")
            decisions, extras, usage = arm_llm(all_cases, args.provider, model, run, raw_dir, args.fresh)
            results.setdefault("llm", []).append({**score(all_cases, decisions, extras), **usage,
                                                  "decisions": decisions, "extras": extras})

    out_dir.mkdir(parents=True, exist_ok=True)
    print()
    print(write_summary(all_cases, items, results, args.provider, model, out_dir))
    print(f"Saved to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
