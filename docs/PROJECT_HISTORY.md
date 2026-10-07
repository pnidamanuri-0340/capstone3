# FinLit Project History

A running log of how this capstone was built, what changed and why, and where things stand.
Add a dated entry at the top of the log whenever you make significant changes.

---

## Current status (2026-10-06)

| Area | Status |
|---|---|
| App | Working end-to-end. Streamlit UI at <http://localhost:8501> |
| AI provider | **OpenAI**: `gpt-4o` (6 specialist agents), `gpt-4o-mini` (router) |
| Market data | **Sample (mock) data**. No Alpha Vantage key yet |
| Automated tests | **71 passing** (offline, no keys needed): `pytest` |
| Live evaluation (OpenAI) | Routing **100%** on 42 labelled questions · Retrieval hit@4 **100%** (MRR 1.0) on 26 · LLM-judge quality **4.0–4.5 / 5** |
| Fresh install from zip | Tested: all 7 smoke checks pass; ~11 min on the dev PC |
| Packaging | `scripts\package.bat` → `dist\finlit.zip` (~100 KB). Guide: [INSTALL_NEW_COMPUTER.md](INSTALL_NEW_COMPUTER.md) |
| VS Code | `.vscode\` launch configs (F5 → "FinLit: Streamlit app"), tasks, test panel |

### How to resume work
1. Open `D:\capstone3` in VS Code (or a terminal in that folder).
2. Run the app: `scripts\run.bat`, or F5 in VS Code.
3. Health check: `.venv\Scripts\finlit smoke` · Tests: `.venv\Scripts\python -m pytest`.
4. Read [ARCHITECTURE.md](ARCHITECTURE.md) before structural changes and [DECISIONS.md](DECISIONS.md) for the reasoning.

### Known environment notes (dev PC)
- `OPENAI_API_KEY` is also set as a **Windows environment variable**, which overrides `.env`. A new PC needs the key in `.env`.
- Stop the app before reinstalling (`pip install -e .`), because Windows locks `finlit.exe`.
- `.env` edits apply on page refresh. Code changes need an app restart.

### Ideas / next steps (not done yet)
- Add a free Alpha Vantage key for live quotes and news (25 requests/day on the free tier).
- Expand the knowledge base (more documents per agent), then run `finlit ingest` and `finlit eval`.
- Add more routing/RAG eval cases, especially multi-topic questions.
- Optional: Docker packaging, and multi-user hosting (currently single-computer, local only).

---

## Log

### 2026-10-06: Built, debugged and packaged (first session)

**Planning**
- Requirements: six specialist agents, LangGraph routing/state, RAG per agent, Alpha Vantage, user
  profiles + memory, MCP server, Streamlit UI, error handling, evaluations, documentation, packaging.
- Decisions made with the user: Anthropic Claude as the LLM (later changed, see below), Chroma with
  local all-MiniLM-L6-v2 embeddings, pip package + install/run scripts (no Docker).

**Built**
- `src/finlit/`: config, LLM factory, agent registry/prompts/router/specialist, LangGraph state/nodes/builder,
  Chroma RAG (one collection per agent) with a curated Markdown knowledge base (79 chunks), Alpha Vantage
  client (cache, rate limit, retries, labelled mock mode), portfolio and goal math, shared services layer,
  SQLite profiles with knowledge-level progression, MCP server, Streamlit UI, CLI, smoke test, eval harness.
- Tests: unit + integration (scripted fake LLMs exercise all 6 routes, tools, memory, failures, MCP, UI).
- Docs: README, CLAUDE.md, ARCHITECTURE, DECISIONS, MCP.
- Adapted to the newer libraries that were installed: mcp 2.x (`MCPServer`), langchain-core 1.x, Streamlit 1.65.

**Problems found and fixed**
| Problem | Cause | Fix |
|---|---|---|
| Chat disabled | No API key in `.env` | Documented key setup. The UI shows a clear banner |
| Anthropic `401 invalid key` | Key incomplete (82 chars). A Claude Pro subscription doesn't include API access | User moved to another provider |
| Claude Sonnet 5.5 rejected requests | It doesn't accept a custom `temperature` | Temperature is now optional and dropped for models that reject it |
| Removed key still being used | Settings were read once at startup | Settings now reload automatically when `.env` changes |
| Added **Google Gemini** provider (free tier) | User asked for a no-cost option | `gemini-3.5-flash` / `-lite`; worked, but the free tier timed out |
| Added **OpenAI** provider | Gemini timeouts | `gpt-4o` / `gpt-4o-mini`; auto order OpenAI → Gemini → Claude |
| Noisy warnings with Gemini | Gemini 3.x ignores temperature; SDK notice | Skip temperature for Gemini 3.x; silence the SDK logger |
| Zip broken on macOS/Linux | PowerShell 5.1 zips use backslash paths | `scripts/package.py` builds the zip with forward slashes |
| App kept working with an empty `.env` in the test install | `OPENAI_API_KEY` also set in Windows environment variables | Documented in the install guide (env vars override `.env`) |

**Verification**
- 71 offline tests pass. A live run of one question per agent (6/6) plus a follow-up memory check passed.
- `finlit eval --judge`: routing 100%, retrieval 100%, answer quality 4.0–4.5/5.
- Clean-folder install from `dist\finlit.zip` passed all smoke checks, including a live OpenAI answer.

**Added for usability**
- `docs/INSTALL_NEW_COMPUTER.md`, `scripts/package.py/.bat` (portable zip).
- `.vscode/` (launch, tasks, settings, extensions) and a README section on running in VS Code.
