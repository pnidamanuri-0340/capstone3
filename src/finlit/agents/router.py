"""Question router: LLM structured output with a keyword fallback."""

from __future__ import annotations

import logging
import re

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from finlit.agents.prompts import router_system_prompt
from finlit.agents.registry import AGENT_KEYS, AGENTS, DEFAULT_AGENT, AgentKey
from finlit.llm import get_chat_model

log = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.35


class RouteDecision(BaseModel):
    """Which specialist agent should answer the user's latest message."""

    agent: AgentKey = Field(description="Key of the specialist agent")
    confidence: float = Field(ge=0, le=1, description="Probability the choice is correct")
    in_scope: bool = Field(default=True, description="False if unrelated to personal finance/investing")
    reason: str = Field(default="", description="One short sentence")


_TICKER_LIST = re.compile(r"\b[A-Z]{1,5}\b(?:\s*(?:,|and|vs\.?|&)\s*\b[A-Z]{1,5}\b)+")


def keyword_route(question: str) -> RouteDecision:
    """Deterministic fallback used when the LLM is unavailable."""
    q = question.lower()
    scores = {k: 0 for k in AGENT_KEYS}
    for key, info in AGENTS.items():
        for kw in info.keywords:
            if kw in q:
                scores[key] += 2 if len(kw) > 4 else 1
    if _TICKER_LIST.search(question):
        scores["market_analysis"] += 2
    # Tax terms dominate generic "what is" phrasing.
    if scores["tax_education"]:
        scores["tax_education"] += 1
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return RouteDecision(agent=DEFAULT_AGENT, confidence=0.3, reason="keyword fallback: no match")
    total = sum(scores.values())
    return RouteDecision(agent=best, confidence=round(scores[best] / total, 2),
                         reason="keyword fallback")


def route_question(question: str, history: list[BaseMessage] | None = None) -> tuple[RouteDecision, str]:
    """Return (decision, method) where method is 'llm' or 'keyword'."""
    recent = ""
    if history:
        tail = [m for m in history[-5:-1]]
        recent = "\n".join(f"{m.type}: {str(m.content)[:300]}" for m in tail)
    prompt = (f"Recent conversation:\n{recent}\n\n" if recent else "") + f"Latest message: {question}"
    try:
        model = get_chat_model("router").with_structured_output(RouteDecision)
        decision = model.invoke([SystemMessage(router_system_prompt()), HumanMessage(prompt)])
        if not isinstance(decision, RouteDecision):
            decision = RouteDecision.model_validate(decision)
        if decision.confidence < MIN_CONFIDENCE and decision.in_scope:
            kw = keyword_route(question)
            if kw.confidence > decision.confidence:
                return kw, "keyword"
        return decision, "llm"
    except Exception as exc:  # noqa: BLE001 - routing must never take the app down
        log.warning("LLM routing failed (%s); using keyword fallback", exc)
        return keyword_route(question), "keyword"
