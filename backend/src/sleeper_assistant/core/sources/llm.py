"""A provider-agnostic LLM client: computed facts in, a strict validated JSON answer out.

The code decides every fact (who is out, the roster, the candidates, the numbers). The model only
writes advice *around* a fixed JSON of those facts, and must answer in the JSON shape of a pydantic
schema. The answer is then checked: it must parse, fit the schema, and pass a caller-supplied check
(for example ``grounded_numbers`` for figures; the caller also checks any player ids against its
own roster). Anything else returns ``None`` so the caller falls back to its deterministic text. The
app never depends on a model being available. Names in the facts come from Sleeper (a team can be
called anything), so callers must treat the facts as data and validate, never trust, the answer.

Configure with environment variables (never commit keys):

- ``LLM_PROVIDER``: ``none`` (default), ``anthropic`` or ``openai_compatible`` (Qwen on Ollama,
  vLLM, OpenRouter, a hosted free tier, ...).
- ``LLM_MODEL``: the model name the provider expects.
- ``LLM_API_KEY`` (``ANTHROPIC_API_KEY`` also works for ``anthropic``).
- ``LLM_BASE_URL``: the OpenAI-compatible server, for example ``http://localhost:11434/v1``.
- ``LLM_MAX_CALLS_PER_RUN``: a cap on calls per process run (default 20), so a bug cannot run up
  a bill. After 3 failures in a row (throttled, down) the run stops asking.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx
from pydantic import BaseModel

from sleeper_assistant.settings import load_settings

log = logging.getLogger(__name__)

PROMPTS = Path(__file__).parents[2] / "prompts"
DEFAULT_CAP = 20
TIMEOUT = 25.0
MAX_FAILURES = 3  # consecutive provider failures after which a run stops asking
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MAX_TOKENS = 2048
EPSILON = 1e-9


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
    settings = load_settings(env)
    provider, model = settings.llm_provider, settings.llm_model
    if provider == "anthropic":
        key = settings.llm_api_key or settings.anthropic_api_key
        if key and model:
            return AnthropicClient(api_key=key, model=model)
    elif provider == "openai_compatible":
        if settings.llm_base_url and model:
            return OpenAICompatibleClient(settings.llm_base_url, model, settings.llm_api_key)
    elif provider != "none":
        log.warning("unknown LLM_PROVIDER %r; the LLM is off", provider)
    return None


def load_prompt(name: str) -> str:
    """A prompt file under ``prompts/``: ``load_prompt("task.v1")`` reads ``task.v1.md``."""
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def extract_json(text: str) -> object:
    """The first JSON object in a reply, tolerating code fences or chatter around it."""
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text, match.start())
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("no JSON object in the reply")


_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?")


def _numbers_in(value: object) -> set[float]:
    found: set[float] = set()
    if isinstance(value, bool):
        return found
    if isinstance(value, int | float):
        found.add(float(value))
    elif isinstance(value, str):
        found.update(float(m) for m in _NUMBER.findall(value))  # "WR12" holds 12
    elif isinstance(value, Mapping):
        for item in value.values():
            found |= _numbers_in(item)
    elif isinstance(value, list | tuple):
        for item in value:
            found |= _numbers_in(item)
    return found


def _matches(written: str, known: float) -> bool:
    places = len(written.split(".")[1]) if "." in written else 0
    return abs(round(float(written), places) - round(known, places)) < EPSILON


def grounded_numbers(texts: list[str], facts: object) -> bool:
    """True when every number written in ``texts`` is one of the facts, allowing for rounding.

    A figure the model invented, or computed itself, fails. A number matches a fact if it is that
    fact rounded to as many decimals as the number is written with (14 or 14.2 for 14.23). Include
    in the facts every figure the advice may quote (projections, gains, ranks).
    """
    allowed = _numbers_in(facts)
    return all(
        any(_matches(number, known) for known in allowed)
        for text in texts
        for number in _NUMBER.findall(text)
    )


class Budget:
    """Caps the calls one run makes and remembers good answers to identical questions.

    Make one per worker run (or request). Only successful answers are remembered, so a failure is
    retried next time; the memory is bounded by the cap.
    """

    def __init__(self, cap: int | None = None) -> None:
        env_cap = load_settings().llm_max_calls
        self.cap = cap if cap is not None else env_cap if env_cap is not None else DEFAULT_CAP
        self.used = 0
        self.failures = 0
        self.answers: dict[str, BaseModel] = {}
        self._lock = threading.Lock()

    def take(self) -> bool:
        with self._lock:
            if self.used >= self.cap or self.failures >= MAX_FAILURES:
                return False
            self.used += 1
            return True


def ask[T: BaseModel](  # noqa: PLR0913 - the optional settings of a call are keyword-only
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
    spent = budget or Budget()
    facts_json = json.dumps(facts, sort_keys=True, default=str)
    key = hashlib.sha256(f"{prompt}\0{facts_json}\0{schema.__name__}".encode()).hexdigest()
    cached = spent.answers.get(key)
    if cached is not None:
        return cached.model_copy(deep=True)  # type: ignore[return-value]
    if not spent.take():
        log.warning("LLM call cap or failure limit reached; using the fallback")
        return None
    system = (
        f"{prompt}\n\nReply with only a JSON object matching this schema:\n"
        f"{json.dumps(schema.model_json_schema())}"
    )
    try:
        reply = client.complete(system, f"FACTS (JSON):\n{facts_json}")
        answer = schema.model_validate(extract_json(reply))
        if check is not None and not check(answer):
            log.warning("LLM answer failed the grounding check; using the fallback")
            return None
    except Exception as error:  # any failure means "use the deterministic text"
        log.warning("LLM call failed (%s); using the fallback", type(error).__name__)
        spent.failures += 1
        return None
    spent.failures = 0
    spent.answers[key] = answer
    return answer.model_copy(deep=True)
