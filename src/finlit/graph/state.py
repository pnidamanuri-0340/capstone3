"""Shared LangGraph state."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class FinState(TypedDict, total=False):
    # Conversation (persisted across turns by the checkpointer)
    messages: Annotated[list[AnyMessage], add_messages]
    user_id: str
    # Per-turn fields (reset by load_profile)
    question: str
    profile: dict
    blocked: bool
    route: str
    route_confidence: float
    route_reason: str
    retrieved: list[dict]
    tool_calls: list[dict]
    answer: str
    citations: list[dict]
    error: str | None
