# LLM second pass experiment

Run on 2026-10-20 14:06. Provider `ollama`, model `qwen2.5:7b`, prompt version `3edc31ee75`.
26 planted cases on 5 pages: 13 anglicisms and 13 correct uses. The rules matched 26 occurrences.

| Arm | Runs | Errors | Error rate | False flags | Missed | Extra findings | Left for review | Calls | Input tokens | Output tokens | Total tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NLP only | 1 | 13.0 | 50% | 13.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 | 0 |
| NLP + LLM second pass | 3 | 7.0 | 27% | 6.0 | 1.0 | 0.0 | 4.0 | 1 | 1373 | 624 | 1997 |
| LLM only (full pages) | 3 | 51.7 (51 to 53) | 78% | 7.7 | 3.3 | 40.7 | 0.0 | 5 | 1875 | 2456 | 4331 |

The second pass cut errors by 46% compared with rules alone.
It used 46% of the tokens of the full page LLM scan.
Errors: second pass 7.0, full page LLM 51.7.
Second pass cost: about 77 tokens per flagged item (the instructions are shared across a batch, so larger batches cost less per item).
Full page cost: about 1029 tokens per 1,000 characters of page text (4,209 characters here). Real pages are often 5,000 to 20,000 characters, so use these two rates to estimate a real site.

How to read this:

- Errors are false flags plus missed anglicisms plus extra findings on text that is meant to be clean.
- The rules treat every match as a flag, so their errors are the correct uses they cannot tell apart.
- "Left for review" is what the LLM marked unsure. It is not counted as an error, but a person still has to check it.
- Half the cases are deliberately ambiguous. Real sites have far fewer, so the error rates here are not real world rates.
- The cases were written by the same person who wrote the prompts. Treat this as a pilot, not a benchmark.

Cases wrong at least once with NLP only: C01, C02, C03, C04, C11, C12, C13, C14, C15, C16, C20, C21, C25
Cases wrong at least once with NLP + LLM second pass: C01, C03, C05, C15, C16, C20, C21
Cases wrong at least once with LLM only (full pages): C01, C02, C03, C04, C07, C09, C10, C12, C15, C20, C25, C26
