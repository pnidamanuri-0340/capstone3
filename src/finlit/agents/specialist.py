"""A specialist agent: RAG retrieval + profile-aware prompt + bounded tool-calling loop."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from finlit.agents.prompts import specialist_system_prompt
from finlit.agents.registry import AGENTS
from finlit.llm import get_chat_model
from finlit.rag.retriever import KnowledgeBaseUnavailable, search
from finlit.tools.langchain_tools import AGENT_TOOLS

log = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5
HISTORY_MESSAGES = 8


@dataclass
class AgentResult:
    answer: str
    citations: list[dict] = field(default_factory=list)
    retrieved: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)


def text_of(message: BaseMessage) -> str:
    """Plain text from a message whose content may be a list of content blocks."""
    content = message.content
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def format_knowledge(hits: list[dict]) -> str:
    return "\n\n".join(f"[{i}] ({h['source']} - {h['section']})\n{h['text']}"
                       for i, h in enumerate(hits, start=1))


class SpecialistAgent:
    def __init__(self, key: str, tools: list[BaseTool] | None = None) -> None:
        if key not in AGENTS:
            raise ValueError(f"Unknown agent {key}")
        self.key = key
        self.info = AGENTS[key]
        self.tools = AGENT_TOOLS[key] if tools is None else tools
        self._tool_map = {t.name: t for t in self.tools}

    def retrieve(self, question: str) -> list[dict]:
        try:
            return search(self.key, question)
        except KnowledgeBaseUnavailable:
            raise
        except Exception:  # noqa: BLE001 - RAG failure should degrade, not crash
            log.exception("Retrieval failed for %s", self.key)
            return []

    def _extra_context(self, profile: dict) -> str:
        if self.key == "portfolio_analysis" and profile.get("holdings"):
            return "SAVED HOLDINGS (JSON): " + json.dumps(profile["holdings"])
        if self.key in ("market_analysis", "news_synthesis") and profile.get("watchlist"):
            return "USER WATCHLIST: " + ", ".join(profile["watchlist"])
        return ""

    def run(self, question: str, history: list[BaseMessage], profile: dict,
            profile_summary: str = "") -> AgentResult:
        hits = self.retrieve(question)
        system = specialist_system_prompt(
            self.key, profile_summary, profile.get("knowledge_level", "beginner"),
            format_knowledge(hits), self._extra_context(profile),
        )
        convo = [m for m in history if isinstance(m, (HumanMessage, AIMessage)) and text_of(m)]
        convo = convo[-HISTORY_MESSAGES:]
        if not convo or not isinstance(convo[-1], HumanMessage):
            convo.append(HumanMessage(question))
        messages: list[BaseMessage] = [SystemMessage(system), *convo]

        model = get_chat_model("agent")
        if self.tools:
            model = model.bind_tools(self.tools)

        tool_log: list[dict] = []
        response: AIMessage | None = None
        for _ in range(MAX_TOOL_ROUNDS):
            response = model.invoke(messages)
            messages.append(response)
            calls = getattr(response, "tool_calls", None) or []
            if not calls:
                break
            for call in calls:
                output = self._run_tool(call["name"], call.get("args", {}))
                tool_log.append({"tool": call["name"], "args": call.get("args", {}),
                                 "output_preview": output[:300]})
                messages.append(ToolMessage(content=output, tool_call_id=call["id"]))
        else:
            # Tool budget exhausted: ask for a final answer without tools.
            messages.append(HumanMessage("Please give your final answer now using the data gathered."))
            response = get_chat_model("agent").invoke(messages)

        answer = text_of(response).strip() if response else ""
        if not answer:
            answer = "I wasn't able to put together an answer. Could you rephrase the question?"
        citations = [{"n": i, "source": h["source"], "section": h["section"], "score": h["score"]}
                     for i, h in enumerate(hits, start=1) if f"[{i}]" in answer]
        return AgentResult(answer, citations, hits, tool_log)

    def _run_tool(self, name: str, args: dict) -> str:
        tool = self._tool_map.get(name)
        if tool is None:
            return json.dumps({"error": f"Unknown tool {name}"})
        try:
            return str(tool.invoke(args))
        except Exception as exc:  # noqa: BLE001 - surface to the LLM, keep the turn alive
            log.exception("Tool %s failed", name)
            return json.dumps({"error": f"Tool {name} failed: {exc}"})


_agents: dict[str, SpecialistAgent] = {}


def get_agent(key: str) -> SpecialistAgent:
    if key not in _agents:
        _agents[key] = SpecialistAgent(key)
    return _agents[key]
