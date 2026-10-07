"""Node functions for the FinLit state graph.

Each node takes the current `FinState` and returns a partial update. Nodes
catch their own expected failures and record them in `error` so a single
bad turn never crashes the conversation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict

from langchain_core.messages import AIMessage, HumanMessage

from finlit import DISCLAIMER
from finlit.agents.registry import AGENT_KEYS, AGENTS
from finlit.agents.router import route_question
from finlit.agents.specialist import get_agent, text_of
from finlit.config import ConfigError
from finlit.memory.profiles import UserProfile, get_store
from finlit.rag.retriever import KnowledgeBaseUnavailable

log = logging.getLogger(__name__)

MAX_QUESTION_CHARS = 4000
DECLINE = "decline"

_DISALLOWED = re.compile(
    r"\b(evade|evading|evasion of)\s+tax|launder|insider (trading )?tip|hide (my )?income from"
    r"|pump[- ]and[- ]dump|fake (receipts|invoices)",
    re.IGNORECASE,
)


# ------------------------------------------------------------------ nodes
def load_profile(state: dict) -> dict:
    """Resolve the latest question and load the user's profile; reset per-turn fields."""
    question = ""
    for m in reversed(state.get("messages", [])):
        if isinstance(m, HumanMessage):
            question = text_of(m).strip()
            break
    user_id = state.get("user_id") or "default"
    try:
        profile = asdict(get_store().get(user_id))
    except Exception:  # noqa: BLE001
        log.exception("Profile load failed")
        profile = asdict(UserProfile(user_id=user_id))
    return {
        "question": question, "user_id": user_id, "profile": profile, "blocked": False,
        "route": "", "route_confidence": 0.0, "route_reason": "", "retrieved": [],
        "tool_calls": [], "answer": "", "citations": [], "error": None,
    }


def guardrail(state: dict) -> dict:
    q = state.get("question", "")
    if not q:
        return {"blocked": True, "answer": "Please type a question about money, investing or taxes."}
    if len(q) > MAX_QUESTION_CHARS:
        return {"blocked": True,
                "answer": f"That message is too long (over {MAX_QUESTION_CHARS} characters). "
                          "Please shorten it or split it into separate questions."}
    if _DISALLOWED.search(q):
        return {"blocked": True,
                "answer": "I can't help with that, because it may involve illegal activity. I'm happy to explain "
                          "legal ways to reduce taxes (like retirement accounts or tax-loss harvesting) "
                          "or how to spot investment fraud."}
    return {"blocked": False}


def router(state: dict) -> dict:
    decision, method = route_question(state["question"], state.get("messages", []))
    if not decision.in_scope:
        return {"route": DECLINE, "route_confidence": decision.confidence,
                "route_reason": decision.reason,
                "answer": "I'm a financial-literacy assistant, so I can help with budgeting, saving, "
                          "investing, markets, financial goals and taxes. What would you like to know "
                          "about your finances?"}
    return {"route": decision.agent, "route_confidence": decision.confidence,
            "route_reason": f"{decision.reason} ({method})"}


def make_agent_node(key: str):
    def agent_node(state: dict) -> dict:
        profile = state.get("profile") or {}
        summary = UserProfile(**profile).summary() if profile else ""
        try:
            result = get_agent(key).run(state["question"], state.get("messages", []), profile, summary)
        except ConfigError as exc:
            return {"error": str(exc)}
        except KnowledgeBaseUnavailable as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            log.exception("Agent %s failed", key)
            return {"error": _friendly_llm_error(exc)}
        return {"answer": result.answer, "citations": result.citations,
                "retrieved": result.retrieved, "tool_calls": result.tool_calls}

    agent_node.__name__ = f"agent_{key}"
    return agent_node


def decline(state: dict) -> dict:
    return {}


def synthesize(state: dict) -> dict:
    """Compose the final reply (answer + sources + disclaimer) and append it to the conversation."""
    route = state.get("route") or ""
    if state.get("error"):
        text = f"Sorry, something went wrong: {state['error']}"
    else:
        text = state.get("answer", "").strip()
        if route in AGENT_KEYS:
            cites = state.get("citations") or []
            if cites:
                text += "\n\n**Sources:** " + "; ".join(
                    f"[{c['n']}] {c['section']} ({c['source'].split('/')[-1]})" for c in cites)
            text += f"\n\n_{DISCLAIMER}_"
    info = AGENTS.get(route)
    meta = {
        "agent": route,
        "agent_name": info.name if info else ("Assistant" if route == DECLINE else "System"),
        "confidence": state.get("route_confidence", 0.0),
        "citations": state.get("citations") or [],
        "tool_calls": [t["tool"] for t in state.get("tool_calls") or []],
        "error": bool(state.get("error")),
    }
    return {"answer": text, "messages": [AIMessage(content=text, additional_kwargs={"finlit": meta})]}


def update_memory(state: dict) -> dict:
    route = state.get("route")
    if route in AGENT_KEYS and not state.get("error"):
        try:
            get_store().record_interaction(state.get("user_id") or "default", route)
        except Exception:  # noqa: BLE001
            log.exception("Profile update failed")
    return {}


# ------------------------------------------------------------- edge logic
def after_guardrail(state: dict) -> str:
    return DECLINE if state.get("blocked") else "router"


def after_router(state: dict) -> str:
    route = state.get("route")
    return f"agent_{route}" if route in AGENT_KEYS else DECLINE


def _friendly_llm_error(exc: Exception) -> str:
    from finlit.config import get_settings

    settings = get_settings()
    name = type(exc).__name__
    msg = str(exc).lower()
    if ("authentication" in name.lower() or "401" in msg or "api key" in msg or "api_key" in msg
            or "permission_denied" in msg):
        return (f"the {settings.provider_label} API key was rejected. "
                f"Check {settings.llm_key_name} in your .env file.")
    if "insufficient_quota" in msg or "billing" in msg:
        return (f"your {settings.provider_label} account has no remaining credit or quota. "
                "Check billing for that API key.")
    if "ratelimit" in name.lower() or "429" in msg or "resource_exhausted" in msg or "quota" in msg:
        return ("the AI service is rate-limiting requests (free tiers have per-minute and daily limits). "
                "Please wait a minute and try again.")
    if "not_found" in msg or ("404" in msg and "model" in msg):
        return (f"the model '{settings.model_for('agent')}' isn't available for your key. "
                "Set a different model in .env.")
    if "overloaded" in msg or "529" in msg or "unavailable" in msg or "503" in msg:
        return "the AI service is temporarily overloaded. Please try again shortly."
    if "connection" in name.lower() or "timeout" in name.lower():
        return "couldn't reach the AI service. Check your internet connection."
    return "an unexpected error occurred while answering. Please try again."
