import asyncio
import json

from finlit.mcp_server.server import mcp
from finlit.tools import services

EXPECTED_TOOLS = {"get_quote", "get_quotes", "get_price_history", "get_company_overview", "get_news",
                  "portfolio_metrics", "rebalance_plan", "goal_projection", "search_knowledge"}


def _call(name, args):
    result = asyncio.run(mcp.call_tool(name, args))
    # mcp 2.x returns CallToolResult; mcp 1.x returns content blocks (or a tuple with structured output)
    if hasattr(result, "content"):
        assert not getattr(result, "is_error", False) and not getattr(result, "isError", False), result
        content = result.content
    else:
        content = result[0] if isinstance(result, tuple) else result
    return json.loads(content[0].text)


def test_mcp_lists_all_tools():
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert EXPECTED_TOOLS <= names


def test_mcp_goal_projection():
    out = _call("goal_projection", {"target": 12000, "years": 1, "annual_rate": 0})
    assert out["required_monthly_savings"] == 1000


def test_mcp_portfolio_metrics_with_mock_prices():
    out = _call("portfolio_metrics", {"holdings": [{"symbol": "VTI", "quantity": 10},
                                                   {"symbol": "BND", "quantity": 5, "asset_class": "bond"}]})
    assert set(out["by_symbol"]) == {"VTI", "BND"}
    assert "performance" in out and out["data_source"].startswith("mock")


def test_mcp_search_knowledge(kb):
    out = _call("search_knowledge", {"agent": "tax_education",
                                       "query": "Health Savings Account HSA triple tax advantaged"})
    assert out["results"][0]["section"].startswith("Health Savings Account")


def test_mcp_search_rejects_unknown_agent():
    assert "error" in _call("search_knowledge", {"agent": "nope", "query": "x"})


def test_rebalance_service_by_asset_class():
    out = services.rebalance_portfolio(
        [{"symbol": "VTI", "quantity": 7, "price": 100}, {"symbol": "BND", "quantity": 3, "price": 100,
                                                          "asset_class": "bond"}],
        {"equity": 60, "bond": 40}, by="asset_class")
    trades = {t["asset"]: t["trade_amount"] for t in out["trades"]}
    assert trades == {"bond": 100.0, "equity": -100.0}


def test_services_return_errors_not_exceptions():
    assert "error" in services.analyze_portfolio([])
    assert "error" in services.plan_goal(1000, 0)
    assert "error" in services.stock_quotes([])
