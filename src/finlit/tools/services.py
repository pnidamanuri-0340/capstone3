"""Finance tool implementations shared by LangChain agents and the MCP server.

Every function returns JSON-serializable dicts and converts expected failures
into `{"error": ...}` instead of raising, so an LLM can explain the problem.
"""

from __future__ import annotations

import logging

from finlit.tools import goal_math, portfolio_math
from finlit.tools.alpha_vantage import MarketDataError, get_client

log = logging.getLogger(__name__)


def _err(exc: Exception) -> dict:
    return {"error": str(exc)}


def stock_quotes(symbols: list[str]) -> dict:
    if not symbols:
        return {"error": "Provide at least one ticker symbol."}
    return get_client().get_quotes(symbols)


def price_history_summary(symbol: str, days: int = 90) -> dict:
    try:
        h = get_client().get_daily_closes(symbol, days=max(5, min(days, 100)))
    except MarketDataError as exc:
        return _err(exc)
    closes = [c for c in h["closes"] if c]
    if len(closes) < 3:
        return {"symbol": symbol, "error": "Not enough price history."}
    rets = portfolio_math.simple_returns(closes)
    return {
        "symbol": h["symbol"],
        "start_date": h["dates"][0],
        "end_date": h["dates"][-1],
        "start_close": closes[0],
        "end_close": closes[-1],
        "period_return": round(portfolio_math.total_return(closes), 4),
        "annualized_volatility": round(portfolio_math.annualized_volatility(rets), 4),
        "max_drawdown": round(portfolio_math.max_drawdown(closes), 4),
        "high": max(closes),
        "low": min(closes),
        "source": h["source"],
    }


def company_overview(symbol: str) -> dict:
    try:
        return get_client().get_overview(symbol)
    except MarketDataError as exc:
        return _err(exc)


def financial_news(tickers: list[str] | None = None, topic: str | None = None, limit: int = 8) -> dict:
    try:
        return get_client().get_news(tickers=tickers, topics=topic, limit=max(1, min(limit, 15)))
    except MarketDataError as exc:
        return _err(exc)


def _to_holdings(raw: list[dict], warnings: list[str]) -> list[portfolio_math.Holding]:
    client = get_client()
    out = []
    for item in raw:
        sym = str(item.get("symbol", "")).upper().strip()
        qty = float(item.get("quantity") or 0)
        if not sym or qty <= 0:
            warnings.append(f"Skipped invalid holding: {item}")
            continue
        price = item.get("price")
        if price in (None, "", 0):
            try:
                price = client.get_quote(sym)["price"]
            except MarketDataError as exc:
                warnings.append(f"No price for {sym}: {exc}")
                continue
        out.append(portfolio_math.Holding(sym, qty, float(price), item.get("asset_class") or "equity"))
    return out


def analyze_portfolio(holdings: list[dict], include_performance: bool = True,
                      risk_free_rate: float = 0.04) -> dict:
    """holdings: [{symbol, quantity, price?, asset_class?}]. Missing prices are fetched."""
    warnings: list[str] = []
    try:
        hs = _to_holdings(holdings, warnings)
        history = None
        if include_performance and hs:
            history = {}
            client = get_client()
            for h in hs:
                try:
                    history[h.symbol] = client.get_daily_closes(h.symbol)["closes"]
                except MarketDataError as exc:
                    warnings.append(f"No history for {h.symbol}: {exc}")
        result = portfolio_math.portfolio_metrics(hs, history or None, risk_free_rate)
    except ValueError as exc:
        return {"error": str(exc), "warnings": warnings}
    result["data_source"] = "mock (sample data, not live)" if get_client().mock else "Alpha Vantage"
    if warnings:
        result["warnings"] = warnings
    return result


def rebalance_portfolio(holdings: list[dict], target_weights: dict[str, float],
                        by: str = "symbol", threshold: float = 0.05) -> dict:
    """Compare current weights with targets (by 'symbol' or 'asset_class')."""
    warnings: list[str] = []
    try:
        hs = _to_holdings(holdings, warnings)
        alloc = portfolio_math.allocation(hs)
    except ValueError as exc:
        return {"error": str(exc), "warnings": warnings}
    total_t = sum(target_weights.values())
    if total_t <= 0:
        return {"error": "Target weights must sum to a positive number."}
    target = {k.upper() if by == "symbol" else k: v / total_t for k, v in target_weights.items()}
    current = alloc["by_symbol"] if by == "symbol" else alloc["by_asset_class"]
    return {
        "total_value": alloc["total_value"],
        "trades": portfolio_math.rebalance_drift(current, target, alloc["total_value"], threshold),
        "note": "Positive trade_amount = buy, negative = sell. Consider taxes and fees before trading.",
        **({"warnings": warnings} if warnings else {}),
    }


def plan_goal(target: float, years: float, annual_rate: float = 0.06, present: float = 0.0,
              monthly_contribution: float | None = None, inflation: float = 0.0) -> dict:
    try:
        return goal_math.goal_projection(target, years, annual_rate, present, monthly_contribution, inflation)
    except ValueError as exc:
        return _err(exc)


def emergency_fund(monthly_expenses: float, months: int = 6, current_savings: float = 0.0) -> dict:
    try:
        tgt = goal_math.emergency_fund_target(monthly_expenses, months)
    except ValueError as exc:
        return _err(exc)
    return {"target": round(tgt, 2), "months_covered": months,
            "current_savings": current_savings, "gap": round(max(0.0, tgt - current_savings), 2)}


def retirement_target(annual_spending: float, withdrawal_rate: float = 0.04,
                      years_until_retirement: float = 0, inflation: float = 0.03) -> dict:
    try:
        future_spend = goal_math.inflation_adjusted(annual_spending, years_until_retirement, inflation)
        number = goal_math.retirement_number(future_spend, withdrawal_rate)
    except ValueError as exc:
        return _err(exc)
    return {"annual_spending_today": annual_spending,
            "annual_spending_at_retirement": round(future_spend, 2),
            "withdrawal_rate": withdrawal_rate, "retirement_target": round(number, 2)}
