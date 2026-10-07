import math

import pytest

from finlit.tools import portfolio_math as pm


def test_allocation_weights_sum_to_one():
    hs = [pm.Holding("VTI", 10, 200, "equity"), pm.Holding("BND", 20, 50, "bond")]
    a = pm.allocation(hs)
    assert a["total_value"] == 3000
    assert a["by_symbol"] == {"VTI": pytest.approx(0.6667, abs=1e-4), "BND": pytest.approx(0.3333, abs=1e-4)}
    assert sum(a["by_asset_class"].values()) == pytest.approx(1.0, abs=1e-3)


def test_allocation_rejects_empty():
    with pytest.raises(ValueError):
        pm.allocation([])


def test_returns_and_drawdown():
    prices = [100, 110, 99, 120]
    assert pm.total_return(prices) == pytest.approx(0.2)
    assert pm.simple_returns(prices)[0] == pytest.approx(0.1)
    assert pm.max_drawdown(prices) == pytest.approx(99 / 110 - 1)


def test_volatility_and_sharpe_constant_series():
    rets = [0.01] * 10
    assert pm.annualized_volatility(rets) == pytest.approx(0.0, abs=1e-12)
    assert pm.sharpe_ratio(rets) == 0.0


def test_annualized_return_one_year():
    prices = [100] + [100] * 251 + [110]
    assert pm.annualized_return(prices) == pytest.approx(0.10, rel=1e-6)


def test_rebalance_drift_trades():
    trades = pm.rebalance_drift({"stocks": 0.7, "bonds": 0.3}, {"stocks": 0.6, "bonds": 0.4}, 10_000)
    by = {t["asset"]: t for t in trades}
    assert by["stocks"]["trade_amount"] == pytest.approx(-1000)
    assert by["bonds"]["trade_amount"] == pytest.approx(1000)
    assert by["stocks"]["needs_rebalance"]


def test_portfolio_metrics_with_history():
    hs = [pm.Holding("A", 1, 100), pm.Holding("B", 1, 100)]
    hist = {"A": [100, 101, 102, 101, 103], "B": [100, 99, 100, 101, 100]}
    m = pm.portfolio_metrics(hs, hist)
    perf = m["performance"]
    assert perf["period_days"] == 4
    assert math.isfinite(perf["sharpe_ratio"])
    assert perf["max_drawdown"] <= 0
