# FinLit Architecture

## 1. System overview

```
             ┌───────────────────────── Streamlit UI (ui/app.py) ─────────────────────────┐
             │ Chat · Profile sidebar · Portfolio editor/charts · Market quotes · Agents   │
             └───────────────┬───────────────────────────────────────┬─────────────────────┘
                             │ graph.stream(messages, thread_id)     │ direct calls
                             ▼                                       ▼
┌──────────────────────── LangGraph StateGraph (graph/) ────────┐   tools/services.py ◄── MCP server
│ load_profile → guardrail ─┬→ router ─┬→ agent_financial_literacy ─┐   │ (mcp_server/server.py)
│                           │          ├→ agent_portfolio_analysis ─┤   │
│                           │          ├→ agent_market_analysis ────┤   ├─ alpha_vantage.py → Alpha Vantage REST
│                           │          ├→ agent_goal_planning ──────┼→ synthesize → update_memory → END
│                           │          ├→ agent_news_synthesis ─────┤   ├─ portfolio_math.py (pure)
│                           │          └→ agent_tax_education ──────┤   └─ goal_math.py (pure)
│                           └──────────┴→ decline ──────────────────┘
│ checkpointer: SqliteSaver (data/checkpoints.sqlite) keyed by "<user>:<thread>"
└───────────────────────────────────────────────────────────────┘
         │ each agent_* node = SpecialistAgent(key)
         ▼
  Chroma (data/chroma) — one collection per agent: finlit_<agent>   ◄── finlit ingest ◄── knowledge/<agent>/*.md
  Profiles (data/finlit.sqlite) — risk, level, goals, holdings, watchlist, topics_seen
  Claude via langchain-anthropic — Haiku 4.5 for routing, Sonnet 5.5 for specialists
```

## 2. State (`graph/state.py`)

| Field | Lifetime | Purpose |
|---|---|---|
| `messages` | persisted (add_messages reducer) | Conversation history; final AI messages carry `additional_kwargs.finlit` metadata (agent, confidence, citations, tools) |
| `user_id` | persisted | Selects the profile |
| `question`, `profile` | per turn | Latest human text and the profile snapshot |
| `blocked`, `route`, `route_confidence`, `route_reason` | per turn | Guardrail and router decisions |
| `retrieved`, `citations`, `tool_calls` | per turn | RAG hits, citations actually used in the answer, tool trace |
| `answer`, `error` | per turn | Specialist output and any user-safe error message |

`load_profile` resets every per-turn field at the start of a turn, so values from the previous turn
never leak into routing (the checkpointer otherwise restores them).

## 3. Node functions (`graph/nodes.py`)

| Node | Responsibility | Failure behaviour |
|---|---|---|
| `load_profile` | Extract latest question; load `UserProfile` from SQLite | Falls back to a default profile |
| `guardrail` | Rejects empty or oversized input and clearly illegal requests (tax evasion, laundering, insider tips) | Sets `blocked` → `decline` |
| `router` | `route_question`: Haiku structured output `RouteDecision{agent, confidence, in_scope, reason}` with recent conversation for follow-ups | LLM error or low confidence (<0.35) → deterministic keyword router; `in_scope=false` → polite redirect |
| `agent_<key>` ×6 | `SpecialistAgent.run`: retrieve → profile-aware system prompt → tool loop (≤5 rounds) → answer + citations | Config, KB and LLM errors become a friendly `error` (auth, rate limit, overload, network are distinguished) |
| `decline` | Pass-through for blocked / out-of-scope turns | — |
| `synthesize` | Adds sources and disclaimer; appends the final `AIMessage` with metadata | Renders `error` as "Sorry, something went wrong: …" |
| `update_memory` | `ProfileStore.record_interaction` (topic counts + level promotion) | Logged, never fatal; skipped for errors and declines |

Conditional edges: `after_guardrail` (blocked → decline) and `after_router` (`agent_<route>` or decline).

## 4. Specialist agents (`agents/`)

All six share one class, `SpecialistAgent`, and differ in **knowledge collection**, **system prompt**
and **tool set** (`tools/langchain_tools.AGENT_TOOLS`). This keeps behaviour consistent and makes it
cheap to add a seventh agent: add a registry entry, a prompt, a knowledge folder and (optionally) tools.

Prompt assembly (`prompts.specialist_system_prompt`):
1. Role-specific instructions (e.g. "call get_stock_quotes once with all tickers").
2. Common rules: ground in excerpts and tools, cite `[n]`, never invent numbers, flag mock data,
   educational framing, Markdown output.
3. Profile summary plus knowledge-level guidance (beginner / intermediate / advanced).
4. Extra context: saved holdings (portfolio agent) or watchlist (market and news agents).
5. Retrieved knowledge excerpts, numbered.

The tool loop is a small explicit loop rather than a prebuilt ReAct agent. This gives control over the
round limit, per-tool error capture (errors go back to the model as JSON), and the tool trace shown in the UI.

## 5. RAG (`rag/`)

- **Corpus**: curated Markdown in `knowledge/<agent>/`. Each `## ` section becomes one chunk prefixed
  with "Document title - Section heading" so the embedding carries topic context.
- **Store**: Chroma `PersistentClient`, one cosine collection per agent (`finlit_<agent>`). Isolation
  stops a tax question from retrieving market-mechanics text, and gives each agent focused, high-precision context.
- **Embeddings**: Chroma's ONNX all-MiniLM-L6-v2 (local, free, no PyTorch). Tests use a deterministic
  hashed bag-of-words embedding so they run offline.
- **Retrieval**: top-k (default 4) with a minimum cosine-similarity threshold (0.25 for ONNX). The answer's
  `[n]` markers are matched back to hits to produce the citations shown in the UI.
- **Interfaces**: `retriever.search()` (plain dicts, used by agents and MCP) and
  `AgentKnowledgeRetriever` (a LangChain `BaseRetriever`).

## 6. External data (`tools/alpha_vantage.py`)

`AlphaVantageClient` wraps `GLOBAL_QUOTE`, `TIME_SERIES_DAILY`, `OVERVIEW` and `NEWS_SENTIMENT` with:
- **TTL cache** per endpoint (60 s quotes, 1 h daily series, 15 min news, 24 h overview).
- **Sliding-window rate limiter** (5 calls/min). It waits up to 15 s, otherwise raises `RateLimitError`.
- **Retries** with exponential backoff (tenacity) for network errors and 5xx responses only.
- **Payload validation**: Alpha Vantage returns HTTP 200 with `Note`/`Information` on rate limits and
  `Error Message` on bad symbols. These map to typed `RateLimitError` and `SymbolNotFoundError`.
- **Mock mode**: deterministic synthetic data labelled `"source": "mock (sample data, not live)"`.
  Live failures are never silently replaced by mock data.

`tools/services.py` is the shared business layer. It returns JSON-safe dicts and converts expected
failures into `{"error": ...}`, so the LangChain tools, the MCP server and the UI all behave the same.

## 7. Memory

- **Short-term / conversation**: LangGraph `SqliteSaver` checkpoints the whole state per
  `thread_id = "<user>:<thread>"`. The UI's "New conversation" button starts a new thread. Specialists see the
  last 8 human/AI messages, and the router sees the last 4 for follow-up resolution.
- **Long-term / profile**: `ProfileStore` (SQLite JSON rows) holds explicit preferences plus learned
  signals (`interactions`, `topics_seen`). Promotion rules raise `knowledge_level`, which changes the
  depth guidance in every specialist prompt. This is how guidance becomes "progressively sophisticated".

## 8. Error-handling summary

| Layer | Strategy |
|---|---|
| Config | `ConfigError` with actionable text; UI banner and disabled chat input instead of a crash |
| Router | LLM → keyword fallback; never raises |
| Tools | Exceptions become JSON errors returned to the LLM, which explains them to the user |
| Agents | Exceptions are classified into friendly messages; the turn completes and the profile is not updated |
| Market data | Typed errors, per-symbol partial results, cache, and rate limiting |
| RAG | Missing collections give "run `finlit ingest`"; the UI auto-ingests on first launch |
| MCP | Logging to stderr only (stdout is the protocol channel); tool errors are returned as data |

## 9. Testing pyramid

- **Unit**: pure math, client parsing and error mapping with fake HTTP sessions, config, profiles,
  chunking/retrieval, router fallback.
- **Integration**: the compiled graph with scripted `GenericFakeChatModel`s exercises all six routes,
  tool calls, memory, decline/guardrail, agent failure and tool failure. Also the MCP tools in-process and
  headless Streamlit (`AppTest`).
- **Smoke**: `finlit smoke` on a real install.
- **Evals**: `finlit eval` measures routing accuracy, retrieval hit-rate/MRR and LLM-as-judge answer quality.
