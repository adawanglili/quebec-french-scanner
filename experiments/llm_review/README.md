# Experiment: an LLM second pass for middle ground terms

Some words are an anglicism in one sentence and correct in the next. *Mail* can mean email or a shopping centre. The rules cannot tell them apart, so they send every match to human review.

This experiment asks one question. If an LLM judges only what the rules matched, does it remove the noise, and how many tokens does that cost compared with an LLM reading every page?

## The test site

Quartier Belvédère is a fictional neighbourhood shopping guide with 5 French pages. It has 26 planted cases of four middle ground terms. 13 are anglicisms and 13 are correct uses.

| Term | Anglicism (flag) | Correct use (ok) |
| --- | --- | --- |
| mail | "Écrivez-nous par mail" → courriel | "Le Mail des Érables", "le mail piétonnier" |
| chat | "Ouvrez le chat en bas de la page" → clavardage | "le chat de la librairie", "nourriture pour chats" |
| booking | "Faites votre booking en ligne" → réservation | "sur Booking.com" |
| spam | "vérifiez votre dossier spam" → pourriel | "le sandwich au Spam" |

The full list with the reason for each label is in `cases.py`. Everything else on the pages is meant to be clean Quebec French, so any other finding counts as an error.

## The three arms

| Arm | What it does | Tokens |
| --- | --- | --- |
| NLP only | The rules match the four terms. Every match is treated as a flag. | 0 |
| NLP + LLM second pass | The rules match first. The LLM gets each match with its sentence and answers flag, ok or unsure. | Only the matched sentences |
| LLM only | The LLM reads the full text of each page and lists the terms to replace. | Every page |

Each LLM arm runs 3 times by default to show how stable the answers are. Temperature is 0.

## Run it

You need a model. Any of these works:

- **Cohere** (default). A free trial key is enough for this test. Create one at [dashboard.cohere.com](https://dashboard.cohere.com/api-keys). Trial keys are rate limited and meant for noncommercial testing.
- **Ollama**. A free model on your own computer. Install [Ollama](https://ollama.com), then run `ollama pull qwen2.5:7b`.
- **Anthropic**. Needs an API key with credit.

From the repo root, in PowerShell:

```powershell
$env:COHERE_API_KEY = "your-trial-key"
python experiments/llm_review/build_site.py
python experiments/llm_review/run.py --provider cohere
```

On macOS or Linux, use `export COHERE_API_KEY=your-trial-key` instead.

For Ollama, run `python experiments/llm_review/run.py --provider ollama`. Pick another model with `--model`.

Results go to `results/<provider>-<model>/`: `summary.md` for reading, `summary.json` for details and `raw/` for every prompt and reply. Saved replies are reused, so running again costs nothing. Add `--fresh` to call the model again.

To check the setup without a model, use `--provider stub`.

## How it is scored

- **Errors** are false flags plus missed anglicisms plus extra findings on clean text.
- **Left for review** is what the LLM marked unsure. It is not an error, but a person still has to check it.
- **Tokens** are the counts the provider reports, not estimates.

The summary also gives the cost per flagged item and the cost per 1,000 characters of page text. Use them to estimate a real site. The second pass grows with the number of flagged items. The full page scan grows with the amount of text.

## Limits

Half the cases are ambiguous on purpose. Real sites have far fewer, so the error rates here are not real world rates. The same person wrote the cases and the prompts, and the site is small. The prompts are fixed before the first run, and the summary records a prompt version so later changes are visible. Treat the result as a pilot that shows the shape of the trade off, not a benchmark.
