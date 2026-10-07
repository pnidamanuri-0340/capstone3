import pytest

from finlit.tools import goal_math as gm


def test_future_value_zero_rate():
    assert gm.future_value(1000, 100, 0.0, 1) == pytest.approx(2200)


def test_required_savings_round_trip():
    pmt = gm.required_monthly_savings(50_000, 5, 0.05, present=5_000)
    assert gm.future_value(5_000, pmt, 0.05, 5) == pytest.approx(50_000, rel=1e-9)


def test_required_savings_already_met():
    assert gm.required_monthly_savings(1000, 5, 0.05, present=10_000) == 0


def test_months_to_goal():
    assert gm.months_to_goal(1200, 100, 0.0) == 12
    assert gm.months_to_goal(10**9, 1, 0.0, max_months=12) is None


def test_retirement_and_emergency():
    assert gm.retirement_number(40_000) == pytest.approx(1_000_000)
    assert gm.emergency_fund_target(3000, 6) == 18000
    with pytest.raises(ValueError):
        gm.retirement_number(40_000, 0)


def test_goal_projection_shortfall():
    p = gm.goal_projection(30_000, 3, 0.0, monthly_contribution=500)
    assert p["required_monthly_savings"] == pytest.approx(833.33, abs=0.01)
    assert p["projected_balance"] == 18_000
    assert p["on_track"] is False
    assert p["shortfall"] == 12_000
