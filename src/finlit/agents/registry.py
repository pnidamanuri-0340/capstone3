"""Single source of truth for the six specialist agents' identities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AgentKey = Literal[
    "financial_literacy",
    "portfolio_analysis",
    "market_analysis",
    "goal_planning",
    "news_synthesis",
    "tax_education",
]

AGENT_KEYS: tuple[str, ...] = (
    "financial_literacy",
    "portfolio_analysis",
    "market_analysis",
    "goal_planning",
    "news_synthesis",
    "tax_education",
)

DEFAULT_AGENT = "financial_literacy"


@dataclass(frozen=True)
class AgentInfo:
    key: str
    name: str
    icon: str
    description: str  # used by the router prompt
    keywords: tuple[str, ...]  # used by the keyword fallback router


AGENTS: dict[str, AgentInfo] = {
    "financial_literacy": AgentInfo(
        "financial_literacy", "Financial Literacy", "📘",
        "Explains personal finance and investing terms and concepts: budgeting, credit scores, "
        "compound interest, APR/APY, stocks, bonds, ETFs, index funds, diversification, inflation.",
        ("what is", "explain", "define", "meaning", "budget", "credit score", "compound", "apr",
         "apy", "etf", "index fund", "mutual fund", "bond", "dividend", "inflation", "debt",
         "emergency fund", "diversif", "expense ratio"),
    ),
    "portfolio_analysis": AgentInfo(
        "portfolio_analysis", "Portfolio Analysis", "📊",
        "Analyzes a user's holdings: asset allocation, weights, concentration, rebalancing, and "
        "performance metrics such as returns, volatility, Sharpe ratio and drawdown.",
        ("my portfolio", "portfolio", "allocation", "holdings", "rebalanc", "sharpe", "volatility",
         "drawdown", "weights", "concentrat", "60/40", "%"),
    ),
    "market_analysis": AgentInfo(
        "market_analysis", "Market Analysis", "📈",
        "Looks up live stock quotes and company fundamentals for one or more tickers and compares "
        "them (price, change, P/E, market cap, beta, recent price trend).",
        ("quote", "price of", "stock price", "trading at", "compare", "ticker", "p/e", "market cap",
         "shares of", "how is", "doing today", "52-week"),
    ),
    "goal_planning": AgentInfo(
        "goal_planning", "Goal Planning", "🎯",
        "Helps set and plan financial goals: saving for a house, retirement targets, emergency "
        "funds, how much to save per month, timelines and projections.",
        ("goal", "save for", "saving for", "how much should i save", "per month", "retire",
         "retirement", "down payment", "house", "college", "plan", "by age", "years"),
    ),
    "news_synthesis": AgentInfo(
        "news_synthesis", "News Synthesizer", "📰",
        "Summarizes and contextualizes recent financial news and market sentiment for companies, "
        "sectors or the economy (Fed, inflation, earnings).",
        ("news", "headline", "latest", "recent", "happening", "why did", "fed", "earnings report",
         "sentiment", "this week"),
    ),
    "tax_education": AgentInfo(
        "tax_education", "Tax Education", "🧾",
        "Explains tax concepts and account types: 401(k), IRA, Roth vs traditional, HSA, 529, "
        "capital gains, tax brackets, deductions, credits, RMDs, tax-loss harvesting.",
        ("tax", "401k", "401(k)", "ira", "roth", "hsa", "529", "capital gain", "deduction",
         "bracket", "rmd", "wash sale", "irs", "write off"),
    ),
}
