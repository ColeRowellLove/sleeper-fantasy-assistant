"""A provider-agnostic LLM client: computed facts in, a strict validated JSON answer out.

The code decides every fact (who is out, the roster, the candidates, the numbers). The model only
writes advice *around* a fixed JSON of those facts, and must answer in the JSON shape of a pydantic
schema. The answer is then checked: it must parse, fit the schema, and pass a caller-supplied check
(see ``grounded_numbers``) that no number or player was made up. Anything else returns ``None`` so
the caller falls back to its deterministic text. The app never depends on a model being available.

Configure with environment variables (never commit keys):

- ``LLM_PROVIDER``: ``none`` (default), ``anthropic`` or ``openai_compatible`` (Qwen on Ollama,
  vLLM, OpenRouter, a hosted free tier, ...).
- ``LLM_MODEL``: the model name the provider expects.
- ``LLM_API_KEY`` (``ANTHROPIC_API_KEY`` also works for ``anthropic``).
- ``LLM_BASE_URL``: the OpenAI-compatible server, for example ``http://localhost:11434/v1``.
- ``LLM_MAX_CALLS_PER_RUN``: a cap on calls per process run (default 50), so a bug cannot run up
  a bill.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx
from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)

PROMPTS = Path(__file__).parent / "prompts"
DEFAULT_CAP = 50
TIMEOUT = 60.0
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MAX_TOKENS = 1024


class LlmClient(Protocol):
    """Anything that turns a system prompt and a user message into text."""

    def complete(self, system: str, user: str) -> str: ...


@dataclass(frozen=True)
class AnthropicClient:
    api_key: str
    model: str
    url: str = ANTHROPIC_URL

    def complete(self, system: str, user: str) -> str:
        response = httpx.post(
            self.url,
            headers={"x-api-key": self.api_key, "anthropic-version": ANTHROPIC_VERSION},
            json={
                "model": self.model,
                "max_tokens": MAX_TOKENS,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        blocks = response.json().get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")


@dataclass(frozen=True)
class OpenAICompatibleClient:
    base_url: str
    model: str
    api_key: str = ""

    def complete(self, system: str, user: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        response = httpx.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": self.model,
                "temperature": 0.2,
                "max_tokens": MAX_TOKENS,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"] or "")


def client_from_env(env: Mapping[str, str] | None = None) -> LlmClient | None:
    """The configured client, or None when no provider is set (or it is incomplete)."""
    values = os.environ if env is None else env
    provider = values.get("LLM_PROVIDER", "none").strip().lower()
    model = values.get("LLM_MODEL", "").strip()
    if provider == "anthropic":
        key = values.get("LLM_API_KEY") or values.get("ANTHROPIC_API_KEY", "")
        if key and model:
            return AnthropicClient(api_key=key, model=model)
    elif provider == "openai_compatible":
        base = values.get("LLM_BASE_URL", "").strip()
        if base and model:
            return OpenAICompatibleClient(base, model, values.get("LLM_API_KEY", ""))
    elif provider != "none":
        log.warning("unknown LLM_PROVIDER %r; the LLM is off", provider)
    return None


def load_prompt(name: str) -> str:
    """A versioned prompt file under ``prompts/`` (``<name>.md``)."""
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> object:
    """The JSON object in a reply, tolerating a code fence or chatter around it."""
    fenced = _JSON_FENCE.search(text)
    candidate = fenced.group(1) if fenced else text
    start, end = candidate.find("{"), candidate.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the reply")
    return json.loads(candidate[start : end + 1])


_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?")


def _numbers_in(value: object) -> set[float]:
    found: set[float] = set()
    if isinstance(value, bool):
        return found
    if isinstance(value, int | float):
        found.add(float(value))
    elif isinstance(value, str):
        found.update(float(m) for m in _NUMBER.findall(value))
    elif isinstance(value, Mapping):
        for item in value.values():
            found |= _numbers_in(item)
    elif isinstance(value, list | tuple):
        for item in value:
            found |= _numbers_in(item)
    return found


def grounded_numbers(texts: list[str], facts: object, tolerance: float = 0.05) -> bool:
    """True when every number written in ``texts`` is one of the facts (to rounding).

    A figure the model invented, or computed itself, fails. Numbers are compared as written, so the
    facts should carry the figures the advice may quote (projections, gains, ranks).
    """
    allowed = _numbers_in(facts)
    return all(
        any(abs(number - known) <= tolerance for known in allowed)
        for text in texts
        for number in _numbers_in(text)
    )


class Budget:
    """Caps the calls one process makes, and remembers answers to identical questions."""

    def __init__(self, cap: int | None = None) -> None:
        env_cap = os.environ.get("LLM_MAX_CALLS_PER_RUN", "")
        self.cap = cap if cap is not None else int(env_cap) if env_cap.isdigit() else DEFAULT_CAP
        self.used = 0
        self.answers: dict[str, BaseModel | None] = {}


DEFAULT_BUDGET = Budget()


def ask[T: BaseModel](  # noqa: PLR0913
    client: LlmClient | None,
    prompt: str,
    facts: object,
    schema: type[T],
    *,
    check: Callable[[T], bool] | None = None,
    budget: Budget | None = None,
) -> T | None:
    """Ask the model about ``facts`` and return its answer as ``schema``, or None.

    None means "use the deterministic text": no client, the call cap reached, a network or provider
    error, a reply that is not valid JSON for the schema, or one the ``check`` rejects. The same
    prompt and facts are answered once per budget (a re-run of the engine costs nothing).
    """
    if client is None:
        return None
    spent = budget or DEFAULT_BUDGET
    facts_json = json.dumps(facts, sort_keys=True, default=str)
    key = hashlib.sha256(f"{prompt}\0{facts_json}\0{schema.__name__}".encode()).hexdigest()
    if key in spent.answers:
        return spent.answers[key]  # type: ignore[return-value]
    if spent.used >= spent.cap:
        log.warning("LLM call cap of %d reached; using the fallback", spent.cap)
        return None
    spent.used += 1
    answer: T | None = None
    system = (
        f"{prompt}\n\nReply with only a JSON object matching this schema:\n"
        f"{json.dumps(schema.model_json_schema())}"
    )
    try:
        reply = client.complete(system, f"FACTS (JSON):\n{facts_json}")
        answer = schema.model_validate(extract_json(reply))
        if check is not None and not check(answer):
            log.warning("LLM answer failed the grounding check; using the fallback")
            answer = None
    except (httpx.HTTPError, ValueError, ValidationError, KeyError, IndexError, TypeError):
        log.exception("LLM call failed; using the fallback")
        answer = None
    spent.answers[key] = answer
    return answer
