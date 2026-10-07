"""Shared fixtures: every test runs offline against a temp data dir, hash embeddings,
mock market data and scripted fake LLMs."""

from __future__ import annotations

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from finlit import llm
from finlit.config import reset_settings_cache


class FakeToolModel(GenericFakeChatModel):
    """Scripted chat model that accepts bind_tools / with_structured_output."""

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self


def fake_model(*responses: AIMessage | str) -> FakeToolModel:
    msgs = [r if isinstance(r, AIMessage) else AIMessage(content=r) for r in responses]
    return FakeToolModel(messages=iter(msgs))


def route_msg(agent: str, confidence: float = 0.9, in_scope: bool = True) -> AIMessage:
    return AIMessage(content="", tool_calls=[{
        "name": "RouteDecision", "id": "route_1",
        "args": {"agent": agent, "confidence": confidence, "in_scope": in_scope, "reason": "test"},
    }])


def _reset_singletons() -> None:
    from finlit.agents import specialist
    from finlit.graph import builder
    from finlit.memory import profiles
    from finlit.rag import store
    from finlit.tools import alpha_vantage

    reset_settings_cache()
    profiles.reset_store()
    alpha_vantage.reset_client()
    store._client.cache_clear()
    builder.get_app.cache_clear()
    specialist._agents.clear()
    llm.clear_overrides()


@pytest.fixture(autouse=True)
def offline_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FINLIT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FINLIT_EMBEDDINGS", "hash")
    monkeypatch.setenv("ALPHA_VANTAGE_MOCK", "true")
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("FINLIT_PROVIDER", "auto")
    _reset_singletons()
    yield
    _reset_singletons()


@pytest.fixture
def kb():
    """Ingest the real knowledge base into the temp Chroma store."""
    from finlit.rag.store import ingest_all

    return ingest_all()
