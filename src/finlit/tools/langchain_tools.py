"""LangChain tool wrappers around `services` for the specialist agents."""

from __future__ import annotations

import json

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from finlit.tools import services


def _j(data) -> str:
    return json.dumps(data, default=str)


class HoldingIn(BaseModel):
    symbol: str = Field(description="Ticker symbol, e.g. VTI")
    quantity: float = Field(description="Number of shares/units")
    price: float | None = Field(default=None, description="Price per share; omit to fetch a quote")
    asset_class: str = Field(default="equity", description="equity, bond, cash, real_estate, ...")


@tool
def get_stock_quotes(symbols: list[str]) -> str:
    """Get the latest quote (price, change, % change, volume) for one or more ticker symbols."""
    return _j(services.stock_quotes(symbols))


@tool
def get_price_history_summary(symbol: str, days: int = 90) -> str:
    """Summarize recent daily price history for a ticker: period return, volatility, max drawdown, high/low."""
    return _j(services.price_history_summary(symbol, days))


@tool
def get_company_overview(symbol: str) -> str:
    """Company fundamentals for a ticker: name, sector, market cap, P/E, dividend yield, beta."""
    return _j(services.company_overview(symbol))


@tool
def get_financial_news(tickers: list[str] | None = None, topic: str | None = None, limit: int = 8) -> str:
    """Recent financial news with sentiment. `tickers` like ["AAPL"]; `topic` one of: economy_macro,
    economy_monetary, financial_markets, earnings, technology, energy_transportation, finance."""
    return _j(services.financial_news(tickers, topic, limit))


@tool
def analyze_portfolio(holdings: list[HoldingIn], include_performance: bool = True) -> str:
    """Compute allocation by symbol and asset class plus performance metrics (return, volatility,
    Sharpe ratio, max drawdown) for a list of holdings."""
    return _j(services.analyze_portfolio([h.model_dump() if isinstance(h, BaseModel) else h
                                          for h in holdings], include_performance))


@tool
def rebalance_portfolio(holdings: list[HoldingIn], target_weights: dict[str, float],
                        by: str = "symbol") -> str:
    """Compare current weights to target weights (keyed by symbol, or by asset class when
    by='asset_class') and return the trades needed to rebalance."""
    return _j(services.rebalance_portfolio([h.model_dump() if isinstance(h, BaseModel) else h
                                            for h in holdings], target_weights, by))


@tool
def project_goal(target: float, years: float, annual_rate: float = 0.06, present: float = 0.0,
                 monthly_contribution: float | None = None, inflation: float = 0.0) -> str:
    """Savings goal projection: required monthly savings to reach `target` in `years`, and if
    `monthly_contribution` is given, the projected balance, shortfall and months to goal.
    Rates are decimals (0.06 = 6%)."""
    return _j(services.plan_goal(target, years, annual_rate, present, monthly_contribution, inflation))


@tool
def emergency_fund_calculator(monthly_expenses: float, months: int = 6, current_savings: float = 0.0) -> str:
    """Emergency fund target and gap for a number of months of expenses."""
    return _j(services.emergency_fund(monthly_expenses, months, current_savings))


@tool
def retirement_target_calculator(annual_spending: float, withdrawal_rate: float = 0.04,
                                 years_until_retirement: float = 0, inflation: float = 0.03) -> str:
    """Estimate a retirement savings target from desired annual spending using a withdrawal rate."""
    return _j(services.retirement_target(annual_spending, withdrawal_rate, years_until_retirement, inflation))


AGENT_TOOLS = {
    "financial_literacy": [],
    "portfolio_analysis": [analyze_portfolio, rebalance_portfolio, get_stock_quotes],
    "market_analysis": [get_stock_quotes, get_price_history_summary, get_company_overview],
    "goal_planning": [project_goal, emergency_fund_calculator, retirement_target_calculator],
    "news_synthesis": [get_financial_news, get_stock_quotes],
    "tax_education": [],
}
