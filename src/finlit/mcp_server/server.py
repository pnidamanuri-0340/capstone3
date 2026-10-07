"""Model Context Protocol server exposing FinLit's finance tools.

Run with `finlit mcp` (stdio transport). See docs/MCP.md for client setup.
The same `finlit.tools.services` functions back both the agents and this
server, so behaviour is identical.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from pydantic import BaseModel, Field

try:  # mcp >= 2.0 renamed FastMCP to MCPServer
    from mcp.server.mcpserver import MCPServer
except ImportError:  # pragma: no cover - mcp 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer

from finlit.agents.registry import AGENT_KEYS
from finlit.rag.retriever import KnowledgeBaseUnavailable, search
from finlit.tools import services

mcp = MCPServer(
    "finlit",
    instructions=(
        "Educational finance tools: stock quotes, price history, company overviews, financial news, "
        "portfolio analytics, goal projections and a curated financial-literacy knowledge base. "
        "Outputs labelled 'mock' are sample data, not live market data."
    ),
)


class Holding(BaseModel):
    symbol: str = Field(description="Ticker symbol, e.g. VTI")
    quantity: float = Field(gt=0, description="Number of shares/units")
    price: float | None = Field(default=None, description="Price per share; omit to fetch a live quote")
    asset_class: str = Field(default="equity", description="equity, bond, cash, real_estate, ...")


@mcp.tool()
def get_quote(symbol: str) -> dict[str, Any]:
    """Latest quote for a single ticker (price, change, % change, volume)."""
    result = services.stock_quotes([symbol])
    if result["quotes"]:
        return result["quotes"][0]
    return {"error": result["errors"][0]["error"] if result["errors"] else "No data"}


@mcp.tool()
def get_quotes(symbols: list[str]) -> dict[str, Any]:
    """Latest quotes for up to 10 tickers. Per-symbol failures are listed under `errors`."""
    return services.stock_quotes(symbols)


@mcp.tool()
def get_price_history(symbol: str, days: int = 90) -> dict[str, Any]:
    """Summary of recent daily prices: period return, annualized volatility, max drawdown, high/low."""
    return services.price_history_summary(symbol, days)


@mcp.tool()
def get_company_overview(symbol: str) -> dict[str, Any]:
    """Company fundamentals: sector, market cap, P/E, dividend yield, beta."""
    return services.company_overview(symbol)


@mcp.tool()
def get_news(tickers: list[str] | None = None, topic: str | None = None, limit: int = 8) -> dict[str, Any]:
    """Recent financial news articles with automated sentiment labels."""
    return services.financial_news(tickers, topic, limit)


@mcp.tool()
def portfolio_metrics(holdings: list[Holding], include_performance: bool = True) -> dict[str, Any]:
    """Allocation by symbol/asset class plus return, volatility, Sharpe ratio and max drawdown."""
    return services.analyze_portfolio([h.model_dump() for h in holdings], include_performance)


@mcp.tool()
def rebalance_plan(holdings: list[Holding], target_weights: dict[str, float],
                   by: str = "symbol") -> dict[str, Any]:
    """Trades needed to move from current weights to target weights (by 'symbol' or 'asset_class')."""
    return services.rebalance_portfolio([h.model_dump() for h in holdings], target_weights, by)


@mcp.tool()
def goal_projection(target: float, years: float, annual_rate: float = 0.06, present: float = 0.0,
                    monthly_contribution: float | None = None, inflation: float = 0.0) -> dict[str, Any]:
    """Required monthly savings for a goal, and projected balance if a contribution is given.
    Rates are decimals (0.06 = 6%)."""
    return services.plan_goal(target, years, annual_rate, present, monthly_contribution, inflation)


@mcp.tool()
def search_knowledge(agent: str, query: str, k: int = 4) -> dict[str, Any]:
    """Search FinLit's curated knowledge base. `agent` is one of: financial_literacy,
    portfolio_analysis, market_analysis, goal_planning, news_synthesis, tax_education."""
    if agent not in AGENT_KEYS:
        return {"error": f"agent must be one of {list(AGENT_KEYS)}"}
    try:
        return {"results": search(agent, query, max(1, min(k, 10)))}
    except KnowledgeBaseUnavailable as exc:
        return {"error": str(exc)}


@mcp.resource("finlit://agents")
def list_agents() -> str:
    """The six specialist knowledge domains."""
    from finlit.agents.registry import AGENTS

    return "\n".join(f"{a.key}: {a.description}" for a in AGENTS.values())


def main() -> None:
    # stdout carries the protocol; logs must go to stderr.
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    mcp.run()


if __name__ == "__main__":
    main()
