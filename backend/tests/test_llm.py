"""The LLM layer: facts in, a validated JSON answer out, and a quiet None on any problem."""

from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel

from sleeper_assistant import llm
from sleeper_assistant.llm import (
    AnthropicClient,
    Budget,
    OpenAICompatibleClient,
    ask,
    client_from_env,
    extract_json,
    grounded_numbers,
    load_prompt,
)


class Advice(BaseModel):
    headline: str
    gain: float


class Fake:
    def __init__(self, reply: str | Exception) -> None:
        self.reply, self.calls = reply, []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def test_no_provider_or_an_incomplete_one_means_no_client() -> None:
    assert client_from_env({}) is None
    assert client_from_env({"LLM_PROVIDER": "none"}) is None
    assert client_from_env({"LLM_PROVIDER": "anthropic", "LLM_MODEL": "m"}) is None  # no key
    assert client_from_env({"LLM_PROVIDER": "openai_compatible", "LLM_MODEL": "m"}) is None
    assert client_from_env({"LLM_PROVIDER": "bogus"}) is None


def test_providers_are_built_from_the_environment() -> None:
    claude = client_from_env(
        {"LLM_PROVIDER": "anthropic", "LLM_MODEL": "m", "ANTHROPIC_API_KEY": "k"}
    )
    assert claude == AnthropicClient("k", "m")
    qwen = client_from_env(
        {"LLM_PROVIDER": "openai_compatible", "LLM_MODEL": "qwen", "LLM_BASE_URL": "http://h/v1"}
    )
    assert qwen == OpenAICompatibleClient("http://h/v1", "qwen", "")


def test_json_is_found_in_a_fence_or_chatter() -> None:
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! {"a": 1} Hope that helps') == {"a": 1}
    with pytest.raises(ValueError, match="no JSON"):
        extract_json("nothing here")


def test_numbers_must_come_from_the_facts() -> None:
    facts = {"projection": 14.2, "rank": 3, "note": "WR12 this week"}
    assert grounded_numbers(["Projected 14.2, ranked 3rd"], facts)
    assert grounded_numbers(["He is WR12"], facts)
    assert not grounded_numbers(["Projected 19.9"], facts)
    assert grounded_numbers(["No figures here"], facts)
    assert grounded_numbers(["about 14 points", "a 14.2 projection"], {"p": 14.23})
    assert not grounded_numbers(["15"], {"p": 14.23})


def test_a_good_answer_is_returned_and_sees_the_facts_and_schema() -> None:
    client = Fake('{"headline": "Start Bo", "gain": 2.5}')
    got = ask(client, "You are a coach.", {"gain": 2.5}, Advice, budget=Budget(5))
    assert got == Advice(headline="Start Bo", gain=2.5)
    system, user = client.calls[0]
    assert "You are a coach." in system and "headline" in system  # the schema is appended
    assert '"gain": 2.5' in user


def test_every_failure_returns_none_instead_of_raising() -> None:
    for reply in [
        "not json",
        '{"headline": "x"}',  # missing gain
        '{"headline": "x", "gain": "lots"}',
        httpx.ConnectError("down"),
        KeyError("choices"),
    ]:
        assert ask(Fake(reply), "p", {}, Advice, budget=Budget(5)) is None
    assert ask(None, "p", {}, Advice) is None


def test_a_failure_is_not_remembered_so_it_is_retried() -> None:
    budget = Budget(5)
    assert ask(Fake("garbage"), "p", {}, Advice, budget=budget) is None
    assert ask(Fake('{"headline": "x", "gain": 1}'), "p", {}, Advice, budget=budget) is not None


def test_a_remembered_answer_is_a_copy() -> None:
    budget = Budget(5)
    client = Fake('{"headline": "x", "gain": 1}')
    first = ask(client, "p", {}, Advice, budget=budget)
    assert first is not None
    first.headline = "edited"
    again = ask(client, "p", {}, Advice, budget=budget)
    assert again is not None and again.headline == "x"


def test_json_after_other_braces_is_still_found() -> None:
    assert extract_json('{not json} then {"a": [1, {"b": 2}]} {"c": 3}') == {"a": [1, {"b": 2}]}


def test_an_answer_the_check_rejects_is_dropped() -> None:
    client = Fake('{"headline": "x", "gain": 9.9}')
    assert (
        ask(client, "p", {"gain": 2}, Advice, check=lambda a: a.gain == 2, budget=Budget(5)) is None
    )


def test_identical_questions_are_answered_once_and_calls_are_capped() -> None:
    client = Fake('{"headline": "x", "gain": 1}')
    budget = Budget(2)
    for _ in range(3):
        assert ask(client, "p", {"n": 1}, Advice, budget=budget) is not None
    assert len(client.calls) == 1  # remembered
    assert ask(client, "p", {"n": 2}, Advice, budget=budget) is not None
    assert ask(client, "p", {"n": 3}, Advice, budget=budget) is None  # cap of 2 reached
    assert len(client.calls) == 2


class _Response:
    def __init__(self, body: dict[str, object]) -> None:
        self.body = body

    def raise_for_status(self) -> None: ...

    def json(self) -> dict[str, object]:
        return self.body


def test_the_anthropic_client_posts_a_message_and_joins_the_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def post(url: str, **kw: object) -> _Response:
        seen.update(url=url, **kw)
        return _Response(
            {"content": [{"type": "text", "text": "{"}, {"type": "text", "text": "}"}]}
        )

    monkeypatch.setattr(httpx, "post", post)
    assert AnthropicClient("k", "m").complete("sys", "hi") == "{}"
    assert seen["headers"]["x-api-key"] == "k"  # type: ignore[index]
    assert seen["json"]["system"] == "sys"  # type: ignore[index]


def test_the_openai_compatible_client_posts_chat_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def post(url: str, **kw: object) -> _Response:
        seen.update(url=url, **kw)
        return _Response({"choices": [{"message": {"content": "{}"}}]})

    monkeypatch.setattr(httpx, "post", post)
    assert OpenAICompatibleClient("http://h/v1/", "qwen").complete("s", "u") == "{}"
    assert seen["url"] == "http://h/v1/chat/completions"
    assert seen["headers"] == {}


def test_prompts_load_from_the_prompts_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path
    (folder / "task.v1.md").write_text("You are a coach.", encoding="utf-8")
    monkeypatch.setattr(llm, "PROMPTS", folder)
    assert load_prompt("task.v1") == "You are a coach."
    with pytest.raises(FileNotFoundError):
        load_prompt("missing.v1")
