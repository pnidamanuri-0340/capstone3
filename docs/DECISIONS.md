# Design Decisions and Reasoning

Short ADR-style notes: the decision, why it was made, and its trade-offs.

### 1. LangGraph router + specialists instead of one big agent
**Why:** Each domain gets a focused prompt, a narrow tool set and its own knowledge base. Smaller tool
menus reduce wrong tool calls, and separate prompts let each agent follow domain rules (e.g. the tax agent
always states the tax year). Explicit graph edges make routing observable (badge plus confidence in the UI)
and testable per route.
**Trade-off:** It adds one extra LLM call per turn for routing. This is mitigated by using the fast Haiku model.

### 2. Structured-output router with keyword fallback
**Why:** Structured output (`RouteDecision`) guarantees a valid agent key, a confidence and an in-scope flag.
The deterministic keyword router keeps the app usable if the LLM call fails, and catches very
low-confidence LLM decisions. It also serves as a measurable baseline in evals (88% on the labelled set).

### 3. One shared `SpecialistAgent` class with an explicit tool loop
**Why:** Six near-identical classes would duplicate logic. A hand-written loop (≤5 rounds) gives exact
control over error capture, the tool trace and a forced final answer when the budget runs out, and it
avoids churn in prebuilt-agent APIs between LangGraph versions.

### 4. A separate vector collection per agent
**Why:** It improves precision (a tax query cannot pull market-mechanics text), allows per-domain
re-ingestion, and matches the requirement for "RAG systems with vector databases for each agent".
**Trade-off:** Cross-domain questions only see one domain's knowledge. The router picks the dominant domain.

### 5. Chroma + local ONNX all-MiniLM-L6-v2 embeddings
**Why:** It's free, offline after one download, has no PyTorch dependency (small install on Windows), and
persists to disk. Offline evaluation measured retrieval hit@4 = 100% and MRR = 1.0 on 26 labelled queries.
**Trade-off:** It's weaker than large hosted embedding models on long or ambiguous queries. The corpus is
small and well-sectioned, so that cost is low here.

### 6. Curated Markdown knowledge base chunked by section
**Why:** "Verified financial knowledge" means content we control and can review. Section-level chunks are
self-contained explanations, and prefixing the title and heading improves embedding context and makes
citations human-readable. Tax figures are labelled with their tax year because they change annually.

### 7. Pluggable LLM provider: OpenAI, Gemini or Claude
**Why:** A capable model for specialists (tool use, careful teaching) and a cheaper, faster one for
routing: GPT-4o / GPT-4o-mini, Gemini 3.5 Flash / Flash-Lite, or Claude Sonnet 5.5 / Haiku 4.5.
Gemini was added so the app runs with a free key. OpenAI was added after the Gemini free tier timed
out in practice; it is the configuration evaluated end-to-end (routing 100% on 42 cases, judge scores
4.0–4.5/5). All model access goes through `llm.get_chat_model`, so the graph, agents and tests don't
depend on the provider. `FINLIT_PROVIDER=auto` picks the first available key (OpenAI → Gemini → Claude).
**Trade-off:** The free tier has rate limits and different data-use terms. Answer style differs
slightly between providers, so `finlit eval` should be re-run after switching.

### 8. Shared `services` layer for agents, MCP and UI
**Why:** One implementation means one set of tests and identical behaviour whether a number comes
from the chat, the Portfolio tab or an external MCP client. Services return `{"error": ...}` instead of raising,
so LLMs can explain failures.

### 9. Mock market data that is always labelled
**Why:** It lets the app, tests and demos run without an Alpha Vantage key or quota. To avoid misleading
users, mock outputs carry `source: "mock (sample data, not live)"` and `[SAMPLE]` headlines, the prompts
require mentioning it, and live errors are never replaced with mock data.

### 10. Defensive Alpha Vantage client
**Why:** The free tier allows 25 requests/day and 5/minute, and signals limits inside HTTP-200 JSON. So the
client caches, rate-limits, retries only transient failures, and maps payload notes to typed errors.
Multi-ticker requests return partial results with per-symbol errors.

### 11. Two kinds of memory
**Why:** Conversation continuity (LangGraph SQLite checkpointer, per thread) is different from knowing
the user (profile store). Profiles hold explicit settings plus learned signals. Rule-based level
promotion is transparent, testable and directly changes prompt depth.

### 12. Guardrails and disclaimers in code, not only in prompts
**Why:** A cheap regex guardrail reliably blocks clearly illegal requests before any LLM call. The
disclaimer is appended by `synthesize`, so it cannot be dropped by the model. The prompts additionally
forbid individualized buy/sell instructions.

### 13. Testing with scripted fake LLMs
**Why:** Deterministic, free, offline tests can cover every graph path, including failure paths that
are hard to trigger with a real model. Real-model quality is measured separately by `finlit eval`
(routing accuracy, LLM-as-judge), which needs a key.

### 14. Packaging as a pip project with install/run scripts
**Why:** A `pyproject.toml` package with a `finlit` console script is the standard, portable way to ship
Python apps. The `.bat` wrappers avoid PowerShell execution-policy problems for non-technical users.
Docker was not required for a single-computer install and would add a heavy prerequisite.
