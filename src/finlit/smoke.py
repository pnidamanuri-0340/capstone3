"""Installation smoke test: `finlit smoke`. Exit code 0 = healthy."""

from __future__ import annotations

import asyncio
import traceback

from finlit.config import get_settings

OK, WARN, FAIL = "PASS", "WARN", "FAIL"


def _check(results: list, name: str, fn) -> None:
    try:
        status, detail = fn()
    except Exception as exc:  # noqa: BLE001
        status, detail = FAIL, f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
    results.append((status, name, detail))


def _imports():
    import chromadb  # noqa: F401
    import langgraph  # noqa: F401
    import streamlit  # noqa: F401
    from finlit.graph.builder import build_graph

    build_graph()
    return OK, "core packages import and the graph compiles"


def _config():
    s = get_settings()
    notes = []
    status = OK
    notes.append(f"AI provider: {s.provider_label} ({s.model_for('agent')} / {s.model_for('router')})")
    if not s.has_llm:
        status = WARN
        notes.append(f"{s.llm_key_name} missing (chat answers disabled)")
    notes.append("market data: " + ("MOCK sample data" if s.use_mock_market_data else "live Alpha Vantage"))
    return status, "; ".join(notes)


def _knowledge():
    from finlit.rag.store import collection_counts

    counts = collection_counts()
    empty = [k for k, v in counts.items() if v == 0]
    if empty:
        return FAIL, f"empty collections: {empty}. Run `finlit ingest`."
    return OK, ", ".join(f"{k}={v}" for k, v in counts.items())


def _retrieval():
    from finlit.rag.retriever import search

    hits = search("tax_education", "Roth IRA contribution limit")
    if not hits:
        return FAIL, "no results for a known query"
    return OK, f"top hit: {hits[0]['section']} (score {hits[0]['score']})"


def _market():
    from finlit.tools.services import stock_quotes

    r = stock_quotes(["AAPL", "MSFT"])
    if r["quotes"]:
        return OK, ", ".join(f"{q['symbol']}={q['price']} [{q['source']}]" for q in r["quotes"])
    return WARN, f"no quotes: {r['errors']}"


def _mcp():
    from finlit.mcp_server.server import mcp

    tools = asyncio.run(mcp.list_tools())
    return OK, f"{len(tools)} tools: " + ", ".join(t.name for t in tools)


def _live_turn():
    s = get_settings()
    if not s.has_llm:
        return WARN, f"skipped (no {s.llm_key_name})"
    from finlit.graph.builder import build_graph, ask
    from langgraph.checkpoint.memory import MemorySaver

    state = ask("What is an index fund?", user_id="smoke", thread_id="smoke",
                app=build_graph(MemorySaver()))
    if state.get("error"):
        return FAIL, state["error"]
    return OK, f"routed to {state['route']}, {len(state['answer'])} chars"


def run_smoke() -> int:
    results: list = []
    for name, fn in [("imports", _imports), ("config", _config), ("knowledge base", _knowledge),
                     ("retrieval", _retrieval), ("market data", _market), ("mcp server", _mcp),
                     ("live LLM turn", _live_turn)]:
        _check(results, name, fn)
    print("\nFinLit smoke test")
    print("-" * 60)
    for status, name, detail in results:
        print(f"[{status}] {name:<15} {detail}")
    failed = sum(1 for s, *_ in results if s == FAIL)
    print("-" * 60)
    print("All checks passed." if not failed else f"{failed} check(s) failed.")
    return 1 if failed else 0
