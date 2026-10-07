# FinLit MCP Server

FinLit exposes its finance tools through the [Model Context Protocol](https://modelcontextprotocol.io),
so any MCP client (Claude Desktop, Claude Code, IDE agents) can use the same quotes, analytics,
calculators and knowledge base that power the in-app agents.

## Implementation

- File: `src/finlit/mcp_server/server.py`
- SDK: official `mcp` Python SDK. It uses `MCPServer` on mcp ≥ 2.0 and falls back to `FastMCP` on 1.x.
- Transport: **stdio** (`finlit mcp`). The client starts the process and exchanges JSON-RPC over stdin/stdout.
- Logging goes to **stderr only**, because any stray `print` to stdout would corrupt the protocol stream.
- Each tool is a thin typed wrapper around `finlit.tools.services`. The SDK generates the JSON Schema for
  inputs from Python type hints and Pydantic models (`Holding`), and validates arguments before
  the function runs.
- Expected failures (bad symbol, rate limit, invalid inputs) are returned as `{"error": "..."}` data
  rather than protocol errors, so the calling model can explain them to the user.

## Tools

| Tool | Inputs | Returns |
|---|---|---|
| `get_quote` | `symbol: str` | price, open/high/low, previous close, change, change %, volume, date, source |
| `get_quotes` | `symbols: list[str]` (≤10) | `{quotes: [...], errors: [{symbol, error}]}` |
| `get_price_history` | `symbol: str, days: int = 90` | period return, annualized volatility, max drawdown, high/low |
| `get_company_overview` | `symbol: str` | name, sector, market cap, P/E, dividend yield, beta |
| `get_news` | `tickers?: list[str], topic?: str, limit: int = 8` | articles with source, date, summary, sentiment |
| `portfolio_metrics` | `holdings: [{symbol, quantity, price?, asset_class?}], include_performance` | allocation by symbol/class, return, volatility, Sharpe, drawdown |
| `rebalance_plan` | `holdings, target_weights: {key: weight}, by: "symbol" \| "asset_class"` | per-asset drift and buy/sell amounts |
| `goal_projection` | `target, years, annual_rate=0.06, present=0, monthly_contribution?, inflation=0` | required monthly savings, projection, shortfall |
| `search_knowledge` | `agent, query, k=4` | top knowledge-base chunks with source/section/score |

Resource: `finlit://agents` lists the six knowledge domains.

## Running and inspecting

```bash
finlit mcp                                   # stdio server (waits for a client)
npx @modelcontextprotocol/inspector .venv/Scripts/finlit.exe mcp   # interactive inspector (Node.js required)
```

## Client configuration

The server reads `.env` from its **working directory**, and many clients do not let you set one. Pass
settings as environment variables instead, and use an **absolute** `FINLIT_DATA_DIR` so the
server finds the knowledge base built by `finlit ingest`.

**Claude Desktop** (`%APPDATA%\Claude\claude_desktop_config.json` on Windows,
`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "finlit": {
      "command": "D:\\capstone3\\.venv\\Scripts\\finlit.exe",
      "args": ["mcp"],
      "env": {
        "FINLIT_DATA_DIR": "D:\\capstone3\\data",
        "ALPHA_VANTAGE_API_KEY": "your-key-or-empty-for-sample-data"
      }
    }
  }
}
```

**Claude Code** (from the project folder):

```bash
claude mcp add finlit -e FINLIT_DATA_DIR=D:/capstone3/data -- D:/capstone3/.venv/Scripts/finlit.exe mcp
```

The MCP server does not need `ANTHROPIC_API_KEY`, because the client's own model does the reasoning.

## Verification

- `pytest tests/integration/test_mcp_and_services.py` lists the tools and calls several in-process.
- `finlit smoke` confirms all 9 tools are registered.
- An end-to-end stdio session (initialize → `list_tools` → `call_tool get_quotes` / `search_knowledge`)
  was run with the SDK's `stdio_client` during development.
