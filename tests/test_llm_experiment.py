"""The LLM second pass experiment runs offline with the stub provider."""

from __future__ import annotations

import sys
from pathlib import Path

EXPERIMENT = Path(__file__).resolve().parent.parent / "experiments" / "llm_review"
sys.path.insert(0, str(EXPERIMENT))

import build_site  # noqa: E402
import run  # noqa: E402
from cases import cases  # noqa: E402


def test_rules_match_every_case_and_nothing_else():
    build_site.main()
    items = run.nlp_matches(cases())
    assert sorted(i["case"] for i in items) == sorted(c["id"] for c in cases())


def test_cases_are_balanced():
    labels = [c["label"] for c in cases()]
    assert labels.count("flag") == labels.count("ok") == 13


def test_stub_run_writes_summary(tmp_path):
    build_site.main()
    assert run.main(["--provider", "stub", "--runs", "1", "--out", str(tmp_path)]) == 0
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "NLP + LLM second pass" in summary
    assert "| NLP only | 1 | 13.0 | 50% |" in summary


def test_prompt_v3_sends_oqlf_records(tmp_path):
    build_site.main()
    assert run.main(["--provider", "stub", "--runs", "1", "--arms", "hybrid",
                     "--prompt", "v3", "--out", str(tmp_path)]) == 0
    import json
    record = json.loads((tmp_path / "raw" / "hybrid-run1-batch1.json").read_text(encoding="utf-8"))
    assert "Judge against the OQLF record given" in record["system"]
    items = json.loads(record["user"])["items"]
    mail = next(i for i in items if i["term"].lower().startswith("mail"))
    assert "galerie marchande" in mail["oqlf_terms"] and "courriel" in mail["oqlf_terms"]
    assert "prompt version `v3-" in (tmp_path / "summary.md").read_text(encoding="utf-8")


def test_prompt_v2_stays_the_default(tmp_path):
    build_site.main()
    assert run.main(["--provider", "stub", "--runs", "1", "--arms", "hybrid", "--out", str(tmp_path)]) == 0
    import json
    record = json.loads((tmp_path / "raw" / "hybrid-run1-batch1.json").read_text(encoding="utf-8"))
    assert "oqlf_terms" not in record["user"]
    assert "prompt version `a2ebc4171b`" in (tmp_path / "summary.md").read_text(encoding="utf-8")
