"""Small clients for the LLM providers used in the experiment.

Each client takes a system prompt and a user message and returns the reply
text with the token counts the provider reports. Keys come from environment
variables, never from files in the repo.

  cohere     COHERE_API_KEY. A free trial key works for noncommercial tests.
  ollama     a local model. Free and private. OLLAMA_HOST, default http://localhost:11434
  anthropic  ANTHROPIC_API_KEY
  stub       no model. Says "flag" to everything. For offline tests only.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

import httpx

DEFAULT_MODELS = {
    "cohere": "command-a-03-2025",
    "ollama": "qwen2.5:7b",
    "anthropic": "claude-haiku-5-5",
    "stub": "stub",
}


@dataclass
class Reply:
    text: str
    input_tokens: int
    output_tokens: int
    seconds: float


def post(url: str, headers: dict, body: dict, timeout: float = 120.0) -> dict:
    """POST with a few retries when the provider says to slow down."""
    for attempt in range(5):
        response = httpx.post(url, headers=headers, json=body, timeout=timeout)
        if response.status_code == 429 or response.status_code >= 500:
            wait = float(response.headers.get("retry-after") or 10 * (attempt + 1))
            print(f"  provider busy ({response.status_code}), waiting {wait:.0f} s")
            time.sleep(wait)
            continue
        if response.status_code >= 400:
            raise RuntimeError(f"{response.status_code} from {url}: {response.text[:500]}")
        return response.json()
    raise RuntimeError(f"Gave up after 5 tries: {url}")


def need_key(name: str) -> str:
    key = os.environ.get(name)
    if not key:
        raise SystemExit(f"Set {name} first. See experiments/llm_review/README.md.")
    return key


def ask(provider: str, model: str, system: str, user: str) -> Reply:
    start = time.monotonic()
    if provider == "cohere":
        data = post(
            "https://api.cohere.com/v2/chat",
            {"Authorization": f"Bearer {need_key('COHERE_API_KEY')}", "Content-Type": "application/json"},
            {
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
        )
        text = "".join(part.get("text", "") for part in data["message"]["content"])
        usage = data.get("usage", {})
        tokens = usage.get("tokens") or usage.get("billed_units") or {}
        return Reply(text, int(tokens.get("input_tokens", 0)), int(tokens.get("output_tokens", 0)),
                     time.monotonic() - start)

    if provider == "ollama":
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        data = post(
            f"{host}/api/chat",
            {"Content-Type": "application/json"},
            {
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0},
            },
            timeout=600.0,
        )
        return Reply(data["message"]["content"], int(data.get("prompt_eval_count", 0)),
                     int(data.get("eval_count", 0)), time.monotonic() - start)

    if provider == "anthropic":
        data = post(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": need_key("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01",
             "Content-Type": "application/json"},
            {
                "model": model,
                "max_tokens": 4000,
                "temperature": 0,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        text = "".join(part.get("text", "") for part in data["content"] if part.get("type") == "text")
        usage = data.get("usage", {})
        return Reply(text, int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0)),
                     time.monotonic() - start)

    if provider == "stub":
        try:
            items = json.loads(user).get("items", [])
        except json.JSONDecodeError:
            items = []
        if items:
            text = json.dumps({"results": [{"id": i["id"], "decision": "flag", "reason": "stub"} for i in items]})
        else:
            text = json.dumps({"findings": []})
        return Reply(text, len(system + user) // 4, len(text) // 4, 0.0)

    raise SystemExit(f"Unknown provider: {provider}")


def parse_json(text: str) -> dict:
    """Read the JSON object in a reply, even with extra text around it."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}
