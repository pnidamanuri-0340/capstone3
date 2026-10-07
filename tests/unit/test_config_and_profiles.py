import pytest

from finlit.config import ConfigError, get_settings, reset_settings_cache
from finlit.memory.profiles import ProfileStore, UserProfile


def test_missing_key_gives_friendly_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    reset_settings_cache()
    s = get_settings()
    assert not s.has_llm
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        s.require_llm()


def test_provider_auto_prefers_google_when_key_set(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g-key")
    reset_settings_cache()
    s = get_settings()
    assert s.provider == "google" and s.has_llm
    assert s.model_for("agent").startswith("gemini") and s.model_for("router").startswith("gemini")
    assert s.llm_key_name == "GOOGLE_API_KEY"


def test_provider_auto_prefers_openai_over_google(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    reset_settings_cache()
    s = get_settings()
    assert s.provider == "openai" and s.llm_key_name == "OPENAI_API_KEY"
    assert (s.model_for("agent"), s.model_for("router")) == ("gpt-4o", "gpt-4o-mini")


def test_openai_model_builds_offline(monkeypatch):
    from langchain_openai import ChatOpenAI

    from finlit.llm import get_chat_model

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    reset_settings_cache()
    m = get_chat_model("agent")
    assert isinstance(m, ChatOpenAI) and m.model_name == "gpt-4o"


def test_forced_provider_overrides_auto(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("FINLIT_PROVIDER", "anthropic")
    reset_settings_cache()
    assert get_settings().provider == "anthropic"


def test_provider_auto_defaults_to_anthropic():
    s = get_settings()
    assert s.provider == "anthropic" and s.model_for("agent").startswith("claude")


def test_explicit_google_without_key_reports_google(monkeypatch):
    monkeypatch.setenv("FINLIT_PROVIDER", "google")
    reset_settings_cache()
    with pytest.raises(ConfigError, match="GOOGLE_API_KEY"):
        get_settings().require_llm()


def test_gemini_model_builds_offline(monkeypatch):
    from langchain_google_genai import ChatGoogleGenerativeAI

    from finlit.llm import get_chat_model

    monkeypatch.setenv("GOOGLE_API_KEY", "g-key")
    reset_settings_cache()
    m = get_chat_model("router")
    assert isinstance(m, ChatGoogleGenerativeAI) and m.model.endswith("gemini-3.5-flash-lite")


def test_settings_reload_when_env_file_changes(tmp_path, monkeypatch):
    import os

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FINLIT_RAG_TOP_K", raising=False)
    env = tmp_path / ".env"
    env.write_text("FINLIT_RAG_TOP_K=3\n", encoding="utf-8")
    reset_settings_cache()
    assert get_settings().rag_top_k == 3
    env.write_text("FINLIT_RAG_TOP_K=7\n", encoding="utf-8")
    st = env.stat()
    os.utime(env, (st.st_atime, st.st_mtime + 5))
    assert get_settings().rag_top_k == 7


def test_mock_market_when_no_av_key():
    assert get_settings().use_mock_market_data


def test_profile_round_trip(tmp_path):
    store = ProfileStore(tmp_path / "p.sqlite")
    p = UserProfile(user_id="u1", name="Sam", risk_tolerance="aggressive",
                    holdings=[{"symbol": "VTI", "quantity": 3}])
    store.save(p)
    got = store.get("u1")
    assert got.name == "Sam" and got.holdings[0]["symbol"] == "VTI"
    assert store.get("nobody").knowledge_level == "beginner"


def test_profile_validation(tmp_path):
    store = ProfileStore(tmp_path / "p.sqlite")
    with pytest.raises(ValueError):
        store.save(UserProfile(user_id="x", risk_tolerance="yolo"))


def test_knowledge_level_progression(tmp_path):
    store = ProfileStore(tmp_path / "p.sqlite")
    agents = ["financial_literacy", "tax_education", "goal_planning"]
    for i in range(9):
        p = store.record_interaction("u", agents[i % 3])
    assert p.knowledge_level == "beginner"
    p = store.record_interaction("u", "financial_literacy")
    assert p.interactions == 10 and p.knowledge_level == "intermediate"


def test_profile_summary_mentions_level_and_holdings():
    s = UserProfile(user_id="u", holdings=[{"symbol": "BND", "quantity": 5}]).summary()
    assert "beginner" in s and "BND" in s
