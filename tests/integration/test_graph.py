"""End-to-end graph runs with scripted LLMs, hash-embedding RAG and mock market data."""

import json

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from finlit import DISCLAIMER, llm
from finlit.agents.registry import AGENT_KEYS
from finlit.graph.builder import ask, build_graph
from finlit.memory.profiles import UserProfile, get_store
from tests.conftest import fake_model, route_msg


@pytest.fixture
def app(kb):
    return build_graph(MemorySaver())


def meta(state):
    return state["messages"][-1].additional_kwargs["finlit"]


@pytest.mark.parametrize("agent", AGENT_KEYS)
def test_each_route_reaches_its_agent(app, agent):
    llm.set_model_override("router", fake_model(route_msg(agent)))
    llm.set_model_override("agent", fake_model(f"Answer from {agent} [1]."))
    state = ask("question", user_id="u", thread_id=agent, app=app)
    assert state["route"] == agent
    assert state["answer"].startswith(f"Answer from {agent}")
    assert DISCLAIMER in state["answer"]
    assert state["retrieved"], "agent should have retrieved knowledge"
    assert state["citations"] and state["citations"][0]["n"] == 1
    assert meta(state)["agent"] == agent


def test_market_agent_calls_quote_tool(app):
    llm.set_model_override("router", fake_model(route_msg("market_analysis")))
    tool_call = AIMessage(content="", tool_calls=[{"name": "get_stock_quotes", "id": "c1",
                                                   "args": {"symbols": ["AAPL", "MSFT"]}}])
    llm.set_model_override("agent", fake_model(tool_call, "| AAPL | MSFT |\n(sample data)"))
    state = ask("Compare AAPL and MSFT", app=app)
    assert [t["tool"] for t in state["tool_calls"]] == ["get_stock_quotes"]
    preview = state["tool_calls"][0]["output_preview"]
    assert "AAPL" in preview and "mock" in preview
    assert meta(state)["tool_calls"] == ["get_stock_quotes"]


def test_portfolio_agent_receives_saved_holdings(app):
    get_store().save(UserProfile(user_id="inv", holdings=[{"symbol": "VTI", "quantity": 10}]))
    llm.set_model_override("router", fake_model(route_msg("portfolio_analysis")))
    agent = fake_model("ok")
    llm.set_model_override("agent", agent)
    from finlit.agents import specialist

    captured = {}
    original = specialist.SpecialistAgent.run

    def spy(self, question, history, profile, summary=""):
        captured["profile"] = profile
        captured["summary"] = summary
        return original(self, question, history, profile, summary)

    specialist.SpecialistAgent.run = spy
    try:
        ask("Analyze my portfolio", user_id="inv", app=app)
    finally:
        specialist.SpecialistAgent.run = original
    assert captured["profile"]["holdings"][0]["symbol"] == "VTI"
    assert "VTI" in captured["summary"]


def test_conversation_memory_across_turns(app):
    llm.set_model_override("router", fake_model(route_msg("financial_literacy"), route_msg("financial_literacy")))
    llm.set_model_override("agent", fake_model("first answer", "second answer"))
    ask("What is an ETF?", user_id="m", thread_id="t", app=app)
    state = ask("And a mutual fund?", user_id="m", thread_id="t", app=app)
    texts = [m.content for m in state["messages"]]
    assert texts[0] == "What is an ETF?" and texts[2] == "And a mutual fund?"
    assert len(state["messages"]) == 4


def test_profile_updated_after_answer(app):
    llm.set_model_override("router", fake_model(route_msg("tax_education")))
    llm.set_model_override("agent", fake_model("tax answer"))
    ask("Roth?", user_id="learner", app=app)
    p = get_store().get("learner")
    assert p.interactions == 1 and p.topics_seen == {"tax_education": 1}


def test_out_of_scope_is_declined(app):
    llm.set_model_override("router", fake_model(route_msg("financial_literacy", in_scope=False)))
    state = ask("Write me a poem about cats", app=app)
    assert state["route"] == "decline"
    assert "financial-literacy assistant" in state["answer"]
    assert get_store().get("default").interactions == 0


def test_guardrail_blocks_illegal_request(app):
    state = ask("How can I evade taxes on my crypto?", app=app)
    assert state["blocked"] and "illegal" in state["answer"]


def test_agent_failure_returns_friendly_error(app):
    class Exploding:
        def bind_tools(self, *_a, **_k):
            return self

        def invoke(self, *_a, **_k):
            raise ConnectionError("connection refused")

    llm.set_model_override("router", fake_model(route_msg("goal_planning")))
    llm.set_model_override("agent", Exploding())
    state = ask("Plan for a house", app=app)
    assert state["error"]
    assert state["answer"].startswith("Sorry, something went wrong")
    assert get_store().get("default").interactions == 0


def test_tool_error_is_reported_to_model_not_raised(app):
    llm.set_model_override("router", fake_model(route_msg("goal_planning")))
    bad = AIMessage(content="", tool_calls=[{"name": "project_goal", "id": "c1",
                                             "args": {"target": 1000, "years": -1}}])
    llm.set_model_override("agent", fake_model(bad, "Years must be positive; please check."))
    state = ask("save 1000 in -1 years", app=app)
    out = json.loads(state["tool_calls"][0]["output_preview"])
    assert "error" in out
    assert "Years must be positive" in state["answer"]
