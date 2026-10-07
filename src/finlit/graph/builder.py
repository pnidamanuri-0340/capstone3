"""Build and run the FinLit LangGraph.

    START -> load_profile -> guardrail -+-> router -+-> agent_<key> (x6) -+-> synthesize -> update_memory -> END
                                        |           |                     |
                                        +-----------+--> decline ---------+
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from finlit.agents.registry import AGENT_KEYS
from finlit.config import get_settings
from finlit.graph import nodes
from finlit.graph.state import FinState


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(FinState)
    g.add_node("load_profile", nodes.load_profile)
    g.add_node("guardrail", nodes.guardrail)
    g.add_node("router", nodes.router)
    g.add_node(nodes.DECLINE, nodes.decline)
    for key in AGENT_KEYS:
        g.add_node(f"agent_{key}", nodes.make_agent_node(key))
    g.add_node("synthesize", nodes.synthesize)
    g.add_node("update_memory", nodes.update_memory)

    g.add_edge(START, "load_profile")
    g.add_edge("load_profile", "guardrail")
    g.add_conditional_edges("guardrail", nodes.after_guardrail,
                            {"router": "router", nodes.DECLINE: nodes.DECLINE})
    g.add_conditional_edges("router", nodes.after_router,
                            {**{f"agent_{k}": f"agent_{k}" for k in AGENT_KEYS},
                             nodes.DECLINE: nodes.DECLINE})
    for key in AGENT_KEYS:
        g.add_edge(f"agent_{key}", "synthesize")
    g.add_edge(nodes.DECLINE, "synthesize")
    g.add_edge("synthesize", "update_memory")
    g.add_edge("update_memory", END)
    return g.compile(checkpointer=checkpointer)


def sqlite_checkpointer() -> BaseCheckpointSaver:
    from langgraph.checkpoint.sqlite import SqliteSaver

    settings = get_settings()
    settings.ensure_dirs()
    conn = sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


@lru_cache(maxsize=1)
def get_app(persistent: bool = True):
    """Compiled graph with conversation memory (SQLite on disk, or in-memory)."""
    return build_graph(sqlite_checkpointer() if persistent else MemorySaver())


def ask(question: str, user_id: str = "default", thread_id: str = "default", app=None) -> dict:
    """Convenience: run one turn and return the final state."""
    app = app or get_app()
    config = {"configurable": {"thread_id": f"{user_id}:{thread_id}"}}
    return app.invoke({"messages": [HumanMessage(question)], "user_id": user_id}, config)
