from pathlib import Path

from sleeper_assistant.settings import DEFAULT_DATABASE_URL, ENV_VARS, load_settings

README = (Path(__file__).parent.parent.parent / "README.md").read_text()
SRC = Path(__file__).parent.parent / "src" / "sleeper_assistant"


def test_defaults_when_nothing_is_set() -> None:
    s = load_settings({})
    assert s.database_url == DEFAULT_DATABASE_URL and s.database_url_raw == ""
    assert (s.llm_provider, s.llm_max_calls, s.boot_allow_shared_db) == ("none", None, False)
    assert s.sleeper_username is None and s.news_feeds == ""


def test_every_variable_is_read() -> None:
    s = load_settings(
        {
            "DATABASE_URL": "postgresql://u:p@h/db",
            "NEWS_FEEDS": " A|https://a.test/rss ",
            "LLM_PROVIDER": " Anthropic ",
            "LLM_MODEL": "m",
            "LLM_API_KEY": "k",
            "ANTHROPIC_API_KEY": "ak",
            "LLM_BASE_URL": " https://x ",
            "LLM_MAX_CALLS_PER_RUN": "7",
            "SLEEPER_USERNAME": "cole",
            "SLEEPER_LEAGUE_ID": "123",
            "BOOT_ALLOW_SHARED_DB": "1",
        }
    )
    assert s.database_url == "postgresql://u:p@h/db" and s.news_feeds == "A|https://a.test/rss"
    assert (s.llm_provider, s.llm_model, s.llm_api_key, s.anthropic_api_key) == (
        "anthropic", "m", "k", "ak",
    )  # fmt: skip
    assert (s.llm_base_url, s.llm_max_calls) == ("https://x", 7)
    assert (s.sleeper_username, s.sleeper_league_id, s.boot_allow_shared_db) == (
        "cole",
        "123",
        True,
    )
    assert load_settings({"LLM_MAX_CALLS_PER_RUN": "many"}).llm_max_calls is None
    assert load_settings({"BOOT_ALLOW_SHARED_DB": "yes"}).boot_allow_shared_db is False


def test_every_variable_is_in_the_readme_table() -> None:
    missing = [name for name in ENV_VARS if f"`{name}`" not in README]
    assert not missing, f"add to the README configuration table: {missing}"


def test_only_settings_reads_the_environment() -> None:
    readers = [
        str(path.relative_to(SRC))
        for path in SRC.rglob("*.py")
        if "os.environ" in path.read_text() and path.name != "settings.py"
    ]
    assert not readers, f"read the environment through settings.py: {readers}"
