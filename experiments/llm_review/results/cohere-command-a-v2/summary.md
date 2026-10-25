# LLM second pass experiment

Run on 2026-10-20 15:14. Provider `cohere`, model `command-a-03-2025`, prompt version `a2ebc4171b`.
26 planted cases on 5 pages: 13 anglicisms and 13 correct uses. The rules matched 26 occurrences.

| Arm | Runs | Errors | Error rate | False flags | Missed | Extra findings | Left for review | Calls | Input tokens | Output tokens | Total tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NLP only | 1 | 13.0 | 50% | 13.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 | 0 |
| NLP + LLM second pass | 3 | 0.0 | 0% | 0.0 | 0.0 | 0.0 | 0.0 | 1 | 1817 | 573 | 2390 |

The second pass cut errors by 100% compared with rules alone.
Second pass cost: about 92 tokens per flagged item (the instructions are shared across a batch, so larger batches cost less per item).

How to read this:

- Errors are false flags plus missed anglicisms plus extra findings on text that is meant to be clean.
- The rules treat every match as a flag, so their errors are the correct uses they cannot tell apart.
- "Left for review" is what the LLM marked unsure. It is not counted as an error, but a person still has to check it.
- Half the cases are deliberately ambiguous. Real sites have far fewer, so the error rates here are not real world rates.
- The cases were written by the same person who wrote the prompts. Treat this as a pilot, not a benchmark.

Cases wrong at least once with NLP only: C01, C02, C03, C04, C11, C12, C13, C14, C15, C16, C20, C21, C25
