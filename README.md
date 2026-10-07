# 💡 FinLit — Multi-Agent Financial Literacy Assistant

FinLit is a local, installable AI app that answers personal-finance questions with a **team of six
specialist agents**. A LangGraph router reads each question (plus recent conversation) and hands it
to the right specialist. Each specialist is grounded by **its own RAG vector store**, can call
**finance tools** (live Alpha Vantage market data, portfolio analytics, goal calculators), and adapts
its explanations to the user's **profile and growing knowledge level**. The same tools are exposed to
other AI clients through a **Model Context Protocol (MCP)** server.

| Agent | What it does | Tools |
|---|---|---|
| 📘 Financial Literacy | Explains personal-finance and investing terms | RAG only |
| 📊 Portfolio Analysis | Allocation, concentration, rebalancing, return/volatility/Sharpe/drawdown | `analyze_portfolio`, `rebalance_portfolio`, `get_stock_quotes` |
| 📈 Market Analysis | Live quotes & fundamentals for one or many stocks, side-by-side | `get_stock_quotes`, `get_price_history_summary`, `get_company_overview` |
| 🎯 Goal Planning | SMART goals, required monthly savings, retirement & emergency-fund targets | `project_goal`, `emergency_fund_calculator`, `retirement_target_calculator` |
| 📰 News Synthesizer | Summarizes and contextualizes recent financial news & sentiment | `get_financial_news`, `get_stock_quotes` |
| 🧾 Tax Education | Tax concepts & account types (401k, IRA, Roth, HSA, 529, capital gains) | RAG only |

> FinLit is an educational tool. It does not provide individualized financial, tax or investment advice.

---

## Quick start (Windows)

1. **Install Python 3.11+** from <https://www.python.org/downloads/>. Tick **"Add python.exe to PATH"**.
2. **Get API keys**:
   - **An AI key** (required for chat). Use any one:
     - **OpenAI (paid)**: <https://platform.openai.com/api-keys>. Uses `gpt-4o` for the agents and `gpt-4o-mini`
       for routing. This is the tested default: 100% routing accuracy and 4.0–4.5/5 answer quality in `finlit eval`.
     - **Google Gemini (free)**: <https://aistudio.google.com/apikey>. Sign in with a Google account
       and click *Create API key*. No credit card is needed. The free tier has per-minute/daily limits, and Google
       may use free-tier prompts to improve its products.
     - **Anthropic Claude (paid)**: <https://console.anthropic.com/> → *API Keys*. A Claude Pro/Max
       subscription does **not** include API usage.
     With `FINLIT_PROVIDER=auto` (the default), FinLit uses the first key it finds in this order: OpenAI, Gemini, Claude.
   - **Alpha Vantage key** (optional, free): <https://www.alphavantage.co/support/#api-key>.
     Without it, FinLit uses clearly labelled **sample** market data.
3. **Install**: double-click `scripts\install.bat` (or run `powershell -ExecutionPolicy Bypass -File scripts\install.ps1`).
   It creates `.venv`, installs everything, asks for your keys, writes `.env`, builds the knowledge base
   and runs a smoke test. The first run downloads about 80 MB for the embedding model.
4. **Run**: double-click `scripts\run.bat`. Your browser opens at <http://localhost:8501>.

> **Moving to another computer?** Run `scripts\package.bat` to build `dist\finlit.zip`, then follow
> **[docs/INSTALL_NEW_COMPUTER.md](docs/INSTALL_NEW_COMPUTER.md)**. It lists what to copy, what not to
> copy (`.venv`, `.env`), and gives step-by-step install, run and troubleshooting instructions.

### macOS / Linux

```bash
bash scripts/install.sh
bash scripts/run.sh
```

### Manual install (any OS)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # then edit .env and add your keys
finlit ingest               # build the per-agent vector stores
finlit ui                   # launch the web app
```

---

## Using the app

- **💬 Chat**: ask anything. Each answer shows which agent replied, the routing confidence, which tools
  ran, cited knowledge excerpts `[1]`, and an expandable "Retrieved knowledge" panel. Follow-ups such as
  "what about MSFT?" use conversation memory.
- **Sidebar profile**: set your name, age, risk tolerance, knowledge level, goals and watchlist. Profiles and
  conversations are stored locally per profile ID. Your knowledge level advances automatically
  (beginner → intermediate after 10 questions across 3+ topics; → advanced after 30 across 5+).
- **📊 Portfolio**: enter holdings (symbol, quantity, optional price, asset class), save, then click
  **Analyze** to see allocation pies and metrics. The Portfolio agent also uses saved holdings, so
  "analyze my portfolio" works in chat.
- **📈 Markets**: quotes for any list of tickers.
- **ℹ️ Agents**: what each specialist covers.

Example questions: *"What is an expense ratio?"*, *"Compare AAPL, MSFT and NVDA"*,
*"I want $40k for a house in 5 years, I have $8k. How much per month?"*, *"Summarize news on the Fed"*,
*"Roth vs traditional IRA for a 25-year-old?"*, *"Analyze my saved portfolio and suggest a 60/40 rebalance"*.

## Running in VS Code

The repo includes ready-made settings in `.vscode/`.

1. Run `scripts\install.bat` once, so that `.venv` exists.
2. In VS Code: **File → Open Folder…** and choose the project folder (the one containing `README.md`).
   Install the recommended Python extensions if prompted.
3. Bottom-right status bar, or **Ctrl+Shift+P → "Python: Select Interpreter"**: choose
   `.venv\Scripts\python.exe` (it should be selected automatically).
4. **Run the app:** open **Run and Debug** (Ctrl+Shift+D), pick **"FinLit: Streamlit app"**, and press **F5**.
   The browser opens at <http://localhost:8501>. Breakpoints in `src/finlit/**` (e.g. `graph/nodes.py`,
   `agents/specialist.py`) pause execution when you ask a question. Press **Shift+F5** to stop.
5. Other launch configs: **ask one question** (prompts for text and prints the answer in the terminal),
   **smoke test**, **evaluations**.
6. **Tests:** the beaker icon (Testing panel) lists all tests. Click ▶ to run, or right-click → *Debug Test*.
7. **Tasks** (Terminal → Run Task…): install, run app, run tests, rebuild knowledge base, smoke test,
   evaluations, build zip.

Only one copy of the app can use port 8501. Close any `run.bat` window before pressing F5.

## Command line

| Command | Purpose |
|---|---|
| `finlit ui [--port 8501]` | Launch the Streamlit app |
| `finlit ask "What is an ETF?"` | One question from the terminal |
| `finlit ingest` | Rebuild vector stores after editing `src/finlit/knowledge/**.md` |
| `finlit mcp` | Run the MCP server over stdio (see [docs/MCP.md](docs/MCP.md)) |
| `finlit smoke` | Installation health check |
| `finlit eval [--offline] [--judge]` | Routing accuracy, retrieval hit-rate, LLM-as-judge answer quality |
| `pytest` | Unit and integration tests (fully offline, no keys needed) |

## Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | (empty) | OpenAI key. One AI key is required for chat |
| `GOOGLE_API_KEY` | (empty) | Gemini key (free tier) |
| `ANTHROPIC_API_KEY` | (empty) | Claude key (paid API) |
| `FINLIT_PROVIDER` | `auto` | `auto` (first key found: OpenAI → Gemini → Claude), `openai`, `google` or `anthropic` |
| `FINLIT_OPENAI_AGENT_MODEL` / `FINLIT_OPENAI_ROUTER_MODEL` | `gpt-4o` / `gpt-4o-mini` | OpenAI models |
| `FINLIT_GEMINI_AGENT_MODEL` / `FINLIT_GEMINI_ROUTER_MODEL` | `gemini-3.5-flash` / `gemini-3.5-flash-lite` | Gemini models |
| `ALPHA_VANTAGE_API_KEY` | (empty) | Live market data; empty means sample data |
| `ALPHA_VANTAGE_MOCK` | `false` | Force sample data even with a key |
| `FINLIT_AGENT_MODEL` | `claude-sonnet-5-5` | Model for the six specialists and judge |
| `FINLIT_ROUTER_MODEL` | `claude-haiku-4-5-20251001` | Fast, cheap model for routing |
| `FINLIT_TEMPERATURE` | (blank) | Specialist sampling temperature; blank = model default |
| `FINLIT_DATA_DIR` | `./data` | Vector store, profiles, conversation checkpoints |
| `FINLIT_EMBEDDINGS` | `onnx` | `onnx` (all-MiniLM-L6-v2) or `hash` (offline test embeddings) |
| `FINLIT_RAG_TOP_K` | `4` | Chunks retrieved per question |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Testing and evaluation

- `pytest` runs 71 offline tests: math, Alpha Vantage parsing / rate-limit / error handling,
  config, profiles and level progression, chunking and retrieval, the router and its fallback, every
  graph route end-to-end with scripted LLMs, tool-error handling, conversation memory, MCP tools,
  and headless Streamlit rendering.
- `finlit eval --offline` measures retrieval hit@4 / MRR on 26 labelled queries (target ≥ 85%) and the
  keyword-router baseline. With an API key, `finlit eval` adds **LLM router accuracy** on 42 labelled
  questions (target ≥ 90%), and `--judge` grades answers for groundedness, relevance, level-fit and
  safety. Reports are saved to `eval_results/`.
- `finlit smoke` checks imports, config, collections, retrieval, market data, MCP tool listing and
  (with a key) one live end-to-end turn.

## Project layout

```
src/finlit/
  config.py  llm.py  cli.py  smoke.py  logging_setup.py
  agents/     registry.py (6 agent identities) · prompts.py · router.py · specialist.py
  graph/      state.py · nodes.py · builder.py   (LangGraph StateGraph + SQLite checkpointer)
  rag/        store.py (Chroma, 1 collection/agent, ingest) · retriever.py · embeddings.py
  knowledge/  <agent>/*.md   curated source documents per agent
  tools/      alpha_vantage.py · portfolio_math.py · goal_math.py · services.py · langchain_tools.py
  memory/     profiles.py   (SQLite user profiles + learning progression)
  mcp_server/ server.py     (MCP tools over stdio)
  ui/         app.py        (Streamlit)
  evals/      run_evals.py + data/*.jsonl
tests/        unit/ · integration/
docs/         ARCHITECTURE.md · MCP.md · DECISIONS.md · INSTALL_NEW_COMPUTER.md
scripts/      install/run for Windows (.ps1/.bat) and macOS/Linux (.sh) · package.py/.bat (portable zip)
```

See **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** for the design, **[docs/DECISIONS.md](docs/DECISIONS.md)**
for the reasoning behind each choice, and **[docs/MCP.md](docs/MCP.md)** for the protocol integration.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "No AI key is set" banner | Add `OPENAI_API_KEY`, `GOOGLE_API_KEY` or `ANTHROPIC_API_KEY` to `.env` in the project folder, save, and refresh the page |
| "API key was rejected" | Re-copy the full key (OpenAI: platform.openai.com; Gemini: aistudio.google.com/apikey; Claude: console.anthropic.com) |
| "no remaining credit or quota" | Add billing/credit to the account that owns the key |
| Gemini requests time out | Free-tier capacity varies. Switch to OpenAI by adding `OPENAI_API_KEY` |
| "rate-limiting requests" with Gemini | Free-tier limit reached. Wait a minute, or try again tomorrow if it's the daily cap |
| "model ... isn't available for your key" | Set `FINLIT_GEMINI_AGENT_MODEL` / `FINLIT_GEMINI_ROUTER_MODEL` to a model your key can use |
| Prices say "mock (sample data, not live)" | Add `ALPHA_VANTAGE_API_KEY` and set `ALPHA_VANTAGE_MOCK=false` |
| "Alpha Vantage rate limit reached" | Free tier is 25 requests/day and 5/minute. Wait, or use mock mode. Quotes are cached for 60 s |
| "Knowledge base ... is missing" | Run `finlit ingest` (from the project folder) |
| `run.ps1 cannot be loaded because running scripts is disabled` | Use the `.bat` files, or `powershell -ExecutionPolicy Bypass -File scripts\run.ps1` |
| Port 8501 in use | `scripts\run.bat -Port 8502` or `finlit ui --port 8502` |
| Start over | Delete the `data/` folder (profiles, chats and vector store), then run `finlit ingest` |
