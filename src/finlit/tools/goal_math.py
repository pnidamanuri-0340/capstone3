"""Time-value-of-money helpers for goal planning."""

from __future__ import annotations


def future_value(present: float, monthly_contribution: float, annual_rate: float, years: float) -> float:
    """FV of a lump sum plus end-of-month contributions, compounded monthly."""
    if years < 0:
        raise ValueError("years must be non-negative")
    n = round(years * 12)
    r = annual_rate / 12
    if r == 0:
        return present + monthly_contribution * n
    growth = (1 + r) ** n
    return present * growth + monthly_contribution * (growth - 1) / r


def required_monthly_savings(target: float, years: float, annual_rate: float, present: float = 0.0) -> float:
    """Monthly contribution needed to reach `target` in `years`."""
    if years <= 0:
        raise ValueError("years must be positive")
    n = round(years * 12)
    r = annual_rate / 12
    if r == 0:
        return max(0.0, (target - present) / n)
    growth = (1 + r) ** n
    needed = target - present * growth
    return max(0.0, needed * r / (growth - 1))


def months_to_goal(target: float, monthly_contribution: float, annual_rate: float,
                   present: float = 0.0, max_months: int = 1200) -> int | None:
    """Months until balance reaches target; None if not reached within max_months."""
    bal, r = present, annual_rate / 12
    for m in range(max_months + 1):
        if bal >= target:
            return m
        bal = bal * (1 + r) + monthly_contribution
    return None


def emergency_fund_target(monthly_expenses: float, months: int = 6) -> float:
    if monthly_expenses < 0:
        raise ValueError("monthly_expenses must be non-negative")
    return monthly_expenses * months


def retirement_number(annual_spending: float, withdrawal_rate: float = 0.04) -> float:
    """Classic 'rule of 25' style target: spending / safe withdrawal rate."""
    if withdrawal_rate <= 0:
        raise ValueError("withdrawal_rate must be positive")
    return annual_spending / withdrawal_rate


def inflation_adjusted(amount: float, years: float, inflation: float = 0.03) -> float:
    return amount * (1 + inflation) ** years


def goal_projection(target: float, years: float, annual_rate: float = 0.06,
                    present: float = 0.0, monthly_contribution: float | None = None,
                    inflation: float = 0.0) -> dict:
    """One-stop summary used by the goal agent and the MCP tool."""
    real_target = inflation_adjusted(target, years, inflation) if inflation else target
    needed = required_monthly_savings(real_target, years, annual_rate, present)
    out = {
        "target": round(target, 2),
        "inflation_adjusted_target": round(real_target, 2),
        "years": years,
        "assumed_annual_return": annual_rate,
        "starting_balance": round(present, 2),
        "required_monthly_savings": round(needed, 2),
    }
    if monthly_contribution is not None:
        fv = future_value(present, monthly_contribution, annual_rate, years)
        out["monthly_contribution"] = round(monthly_contribution, 2)
        out["projected_balance"] = round(fv, 2)
        out["on_track"] = fv >= real_target
        out["shortfall"] = round(max(0.0, real_target - fv), 2)
        out["months_to_goal_at_this_rate"] = months_to_goal(real_target, monthly_contribution, annual_rate, present)
    return out
