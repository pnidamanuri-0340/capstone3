# CLAUDE.md

Guidance for AI coding assistants working in this repository.

## What this is
FinLit: a multi-agent financial-literacy app. A LangGraph router sends each question to one of six
specialist agents (RAG plus tools), with a Streamlit UI, Alpha Vantage market data, SQLite memory/profiles
and an MCP server. Read `docs/ARCHITECTURE.md` before structural changes and `docs/DECISIONS.md` for why
things are the way they are.

## Resuming work
Read `docs/PROJECT_HISTORY.md` first: current status, past problems and fixes, next steps. Add a dated
log entry there after significant changes.

## Commands (Windows paths; use `.venv/bin/` on macOS/Linux)
- Install: `scripts\install.bat` or `.venv\Scripts\pip install -e ".[dev]"`
- Tests (offline, no keys): `.venv\Scripts\python -m pytest`
- Rebuild vector stores after editing knowledge: `.venv\Scripts\finlit ingest`
- Health check: `.venv\Scripts\finlit smoke`
- Evals: `.venv\Scripts\finlit eval --offline` (or without `--offline` / with `--judge` when a key is set)
- Run UI: `.venv\Scripts\finlit ui`; MCP server: `.venv\Scripts\finlit mcp`

## Conventions
- Agent identity lives only in `agents/registry.py` (`AGENT_KEYS`, `AGENTS`). Adding an agent means:
  a registry entry, a prompt in `agents/prompts.py`, a `knowledge/<key>/` folder, an `AGENT_TOOLS` entry,
  routing eval cases, then `finlit ingest`. The graph builds nodes from the registry automatically.
- Business logic goes in `tools/services.py` (returns dicts and `{"error": ...}`; never raises for expected
  failures). `langchain_tools.py` and `mcp_server/server.py` stay thin wrappers.
- `portfolio_math.py` and `goal_math.py` are pure functions. Keep them I/O-free and unit-tested.
- All LLM access goes through `llm.get_chat_model(role)`. The provider is OpenAI, Gemini or Claude
  (`Settings.provider`; `auto` = first key in `config.AUTO_ORDER`). Provider metadata lives in
  `config.PROVIDERS`. Tests inject fakes with `llm.set_model_override`.
- Never present mock data as live. Keep the `source` labels.
- The MCP server must not write to stdout (it is the protocol channel).
- Tests must stay offline: `tests/conftest.py` forces hash embeddings, mock market data and a temp data dir.
- Knowledge-base facts with yearly limits must name the tax year.

## Gotchas
- Installed `mcp` is 2.x (`MCPServer`). The server falls back to `FastMCP` for 1.x.
- Streamlit ≥1.50: use `width="stretch"`, not the deprecated `use_container_width`.
- Settings are cached (`get_settings`). Call `reset_settings_cache()` after changing env vars in tests.
- The `.env` file is read from the current working directory. Scripts `cd` to the project root first.
