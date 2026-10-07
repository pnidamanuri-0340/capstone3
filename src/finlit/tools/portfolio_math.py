"""Pure portfolio analytics. No I/O, so it is easy to test and reuse from MCP."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

TRADING_DAYS = 252


@dataclass
class Holding:
    symbol: str
    quantity: float
    price: float
    asset_class: str = "equity"

    @property
    def value(self) -> float:
        return self.quantity * self.price


def allocation(holdings: list[Holding]) -> dict:
    """Weights by symbol and by asset class. Raises ValueError on empty/zero portfolios."""
    total = sum(h.value for h in holdings)
    if not holdings or total <= 0:
        raise ValueError("Portfolio must contain at least one holding with positive value.")
    by_symbol: dict[str, float] = {}
    by_class: dict[str, float] = {}
    for h in holdings:
        by_symbol[h.symbol.upper()] = by_symbol.get(h.symbol.upper(), 0.0) + h.value / total
        by_class[h.asset_class] = by_class.get(h.asset_class, 0.0) + h.value / total
    return {
        "total_value": round(total, 2),
        "by_symbol": {k: round(v, 4) for k, v in by_symbol.items()},
        "by_asset_class": {k: round(v, 4) for k, v in by_class.items()},
    }


def simple_returns(prices: list[float]) -> list[float]:
    if len(prices) < 2:
        return []
    return [(b - a) / a for a, b in zip(prices[:-1], prices[1:]) if a]


def total_return(prices: list[float]) -> float:
    if len(prices) < 2 or not prices[0]:
        raise ValueError("Need at least two prices with a non-zero start.")
    return prices[-1] / prices[0] - 1


def annualized_return(prices: list[float], periods_per_year: int = TRADING_DAYS) -> float:
    n = len(prices) - 1
    if n <= 0:
        raise ValueError("Need at least two prices.")
    return (1 + total_return(prices)) ** (periods_per_year / n) - 1


def annualized_volatility(returns: list[float], periods_per_year: int = TRADING_DAYS) -> float:
    if len(returns) < 2:
        raise ValueError("Need at least two returns to compute volatility.")
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(var) * math.sqrt(periods_per_year)


def sharpe_ratio(returns: list[float], risk_free_rate: float = 0.04,
                 periods_per_year: int = TRADING_DAYS) -> float:
    vol = annualized_volatility(returns, periods_per_year)
    if vol == 0:
        return 0.0
    ann_mean = (sum(returns) / len(returns)) * periods_per_year
    return (ann_mean - risk_free_rate) / vol


def max_drawdown(prices: list[float]) -> float:
    """Largest peak-to-trough decline as a negative fraction (e.g. -0.25)."""
    if not prices:
        raise ValueError("Need prices.")
    peak = prices[0]
    worst = 0.0
    for p in prices:
        peak = max(peak, p)
        if peak:
            worst = min(worst, p / peak - 1)
    return worst


def portfolio_series(price_history: dict[str, list[float]], weights: dict[str, float]) -> list[float]:
    """Value of $1 invested with fixed weights (daily-rebalanced approximation)."""
    symbols = [s for s in weights if s in price_history and price_history[s]]
    if not symbols:
        raise ValueError("No price history for the weighted symbols.")
    n = min(len(price_history[s]) for s in symbols)
    wsum = sum(weights[s] for s in symbols)
    value = [1.0]
    for i in range(1, n):
        r = sum(
            weights[s] / wsum * (price_history[s][i] / price_history[s][i - 1] - 1)
            for s in symbols
        )
        value.append(value[-1] * (1 + r))
    return value


def rebalance_drift(current: dict[str, float], target: dict[str, float],
                    total_value: float, threshold: float = 0.05) -> list[dict]:
    """Trades needed to return to target weights; flags positions drifting beyond threshold."""
    out = []
    for key in sorted(set(current) | set(target)):
        cur, tgt = current.get(key, 0.0), target.get(key, 0.0)
        drift = cur - tgt
        out.append({
            "asset": key,
            "current_weight": round(cur, 4),
            "target_weight": round(tgt, 4),
            "drift": round(drift, 4),
            "needs_rebalance": abs(drift) >= threshold,
            "trade_amount": round(-drift * total_value, 2),
        })
    return out


def portfolio_metrics(holdings: list[Holding],
                      price_history: dict[str, list[float]] | None = None,
                      risk_free_rate: float = 0.04) -> dict:
    result = {"holdings": [asdict(h) | {"value": round(h.value, 2)} for h in holdings]}
    result.update(allocation(holdings))
    if price_history:
        series = portfolio_series(price_history, result["by_symbol"])
        rets = simple_returns(series)
        if len(rets) >= 2:
            result["performance"] = {
                "period_days": len(series) - 1,
                "total_return": round(total_return(series), 4),
                "annualized_return": round(annualized_return(series), 4),
                "annualized_volatility": round(annualized_volatility(rets), 4),
                "sharpe_ratio": round(sharpe_ratio(rets, risk_free_rate), 3),
                "max_drawdown": round(max_drawdown(series), 4),
            }
    return result
