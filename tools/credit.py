"""Deterministic private-credit underwriting, valuation, and monitoring tools.

The assumptions are deliberately explicit. Default probabilities are synthetic
calibration aids until a user supplies observed performance data.
"""

from __future__ import annotations

import json
from typing import Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


def _artifact(title: str, subtitle: str, columns: list[str], rows: list[dict], summary: dict) -> str:
    return "__ARTIFACT__" + json.dumps({
        "kind": "table", "title": title, "subtitle": subtitle,
        "columns": columns, "rows": rows, "summary": summary,
        "disclosure": "Synthetic calibration — not an empirical probability or investment recommendation.",
    })


def _irr(cashflows: list[float]) -> float | None:
    def npv(rate: float) -> float:
        return sum(cf / ((1 + rate) ** i) for i, cf in enumerate(cashflows))
    lo, hi = -0.95, 10.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(100):
        mid = (lo + hi) / 2
        if abs(npv(mid)) < 0.01:
            return mid
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return mid


class CreditScreenArgs(BaseModel):
    strategy: Literal["direct_lending", "abl", "real_estate", "infrastructure", "fund_finance", "specialty_finance", "distressed"]
    amount: float = Field(gt=0)
    ebitda: float = Field(default=0, ge=0)
    enterprise_value: float = Field(default=0, ge=0)
    recurring_revenue_pct: float = Field(default=50, ge=0, le=100)
    sponsor_backed: bool = True
    requested_spread_bps: int = Field(default=650, ge=0)


def _screen_credit_opportunity(**kw) -> str:
    a = CreditScreenArgs(**kw)
    leverage = a.amount / a.ebitda if a.ebitda else None
    ltv = a.amount / a.enterprise_value * 100 if a.enterprise_value else None
    score = 50 + (10 if a.sponsor_backed else 0) + (10 if a.recurring_revenue_pct >= 60 else 0)
    score += 10 if a.requested_spread_bps >= 600 else 0
    if leverage is not None:
        score += 15 if leverage <= 4.5 else (5 if leverage <= 6 else -15)
    if ltv is not None:
        score += 10 if ltv <= 55 else (-10 if ltv > 75 else 0)
    score = max(0, min(100, score))
    decision = "Pursue" if score >= 70 else ("Review" if score >= 50 else "Decline")
    return json.dumps({"decision": decision, "score": score, "strategy": a.strategy,
                       "leverage_x": round(leverage, 2) if leverage else None,
                       "ltv_pct": round(ltv, 2) if ltv else None,
                       "synthetic_calibration": True})


screen_credit_opportunity = StructuredTool.from_function(
    func=_screen_credit_opportunity, name="screen_credit_opportunity",
    description="Screen a non-venture private-credit opportunity for mandate fit and preliminary repayment risk.",
    args_schema=CreditScreenArgs,
)


class DefaultRiskArgs(BaseModel):
    leverage_x: float = Field(ge=0)
    interest_cover_x: float = Field(gt=0)
    revenue_growth_pct: float = 0
    recurring_revenue_pct: float = Field(default=50, ge=0, le=100)
    sponsor_support: Literal["strong", "moderate", "weak", "none"] = "moderate"
    collateral_coverage_x: float = Field(default=1, ge=0)
    ead: float = Field(gt=0)


PD_BY_GRADE = {"1": 0.25, "2": 0.75, "3": 1.50, "4": 3.00, "5": 6.00, "6": 12.00, "7": 25.00, "8": 50.00}


def _model_default_risk(**kw) -> str:
    a = DefaultRiskArgs(**kw)
    points = 1
    points += 0 if a.leverage_x <= 3 else (1 if a.leverage_x <= 4.5 else 2 if a.leverage_x <= 6 else 4)
    points += 0 if a.interest_cover_x >= 3 else (1 if a.interest_cover_x >= 2 else 2 if a.interest_cover_x >= 1.25 else 4)
    points += 1 if a.revenue_growth_pct < 0 else 0
    points += 1 if a.recurring_revenue_pct < 40 else 0
    points += {"strong": 0, "moderate": 1, "weak": 2, "none": 3}[a.sponsor_support]
    grade = str(max(1, min(8, points)))
    pd_pct = PD_BY_GRADE[grade]
    lgd_pct = max(10, min(90, 55 - 20 * (a.collateral_coverage_x - 1)))
    expected_loss = a.ead * pd_pct / 100 * lgd_pct / 100
    return json.dumps({"obligor_grade": grade, "pd_pct": pd_pct,
                       "facility_lgd_pct": round(lgd_pct, 2), "ead": a.ead,
                       "expected_loss": round(expected_loss, 2), "synthetic_calibration": True,
                       "drivers": {"leverage_x": a.leverage_x, "interest_cover_x": a.interest_cover_x,
                                   "sponsor_support": a.sponsor_support, "collateral_coverage_x": a.collateral_coverage_x}})


model_default_risk = StructuredTool.from_function(
    func=_model_default_risk, name="model_default_risk",
    description="Produce an explainable synthetic-calibration obligor grade, PD, facility LGD and expected loss.",
    args_schema=DefaultRiskArgs,
)


class DebtCashflowArgs(BaseModel):
    principal: float = Field(gt=0)
    term_years: int = Field(default=5, ge=1, le=30)
    base_rate_pct: float = Field(default=3.0, ge=0)
    spread_bps: int = Field(default=650, ge=0)
    floor_pct: float = Field(default=0, ge=0)
    cash_interest_pct: float | None = Field(default=None, ge=0)
    pik_interest_pct: float = Field(default=0, ge=0)
    amortization_pct: float = Field(default=0, ge=0, le=100)
    oid_pct: float = Field(default=100, gt=0, le=100)
    upfront_fee_pct: float = Field(default=0, ge=0, le=20)
    prepay_year: int | None = Field(default=None, ge=1, le=30)


def _model_debt_cashflows(**kw) -> str:
    a = DebtCashflowArgs(**kw)
    term = min(a.term_years, a.prepay_year or a.term_years)
    rate = a.cash_interest_pct if a.cash_interest_pct is not None else max(a.base_rate_pct, a.floor_pct) + a.spread_bps / 100
    balance = a.principal
    rows, lender_cfs = [], [-(a.principal * a.oid_pct / 100) + a.principal * a.upfront_fee_pct / 100]
    annual_amort = a.principal * a.amortization_pct / 100
    for year in range(1, term + 1):
        opening = balance
        cash_interest = opening * rate / 100
        pik = opening * a.pik_interest_pct / 100
        balance += pik
        principal_pay = balance if year == term else min(balance, annual_amort)
        balance -= principal_pay
        lender_cfs.append(cash_interest + principal_pay)
        rows.append({"year": year, "opening_balance": round(opening, 2), "cash_interest": round(cash_interest, 2),
                     "pik_interest": round(pik, 2), "principal": round(principal_pay, 2), "closing_balance": round(balance, 2)})
    irr = _irr(lender_cfs)
    return _artifact("Debt cash-flow schedule", f"{term} years · {rate:.2f}% cash coupon",
                     ["year", "opening_balance", "cash_interest", "pik_interest", "principal", "closing_balance"], rows,
                     {"cash_coupon_pct": round(rate, 3), "lender_irr_pct": round(irr * 100, 3) if irr is not None else None,
                      "total_cash_interest": round(sum(r["cash_interest"] for r in rows), 2), "synthetic_calibration": True})


model_debt_cashflows = StructuredTool.from_function(
    func=_model_debt_cashflows, name="model_debt_cashflows",
    description="Build deterministic private-debt cash flows and lender IRR including floating rates, floor, PIK, amortization, OID, fees and prepayment.",
    args_schema=DebtCashflowArgs,
)


class CovenantArgs(BaseModel):
    debt: float = Field(gt=0)
    ebitda: float = Field(gt=0)
    cash_interest: float = Field(gt=0)
    scheduled_principal: float = Field(default=0, ge=0)
    capex: float = Field(default=0, ge=0)
    cash_taxes: float = Field(default=0, ge=0)
    liquidity: float = Field(default=0, ge=0)
    max_leverage_x: float = Field(default=5.5, gt=0)
    min_interest_cover_x: float = Field(default=1.75, gt=0)
    min_dscr_x: float = Field(default=1.2, gt=0)
    min_liquidity: float = Field(default=0, ge=0)
    downside_pct: float = Field(default=0, ge=0, le=100)


def _test_covenant_headroom(**kw) -> str:
    a = CovenantArgs(**kw)
    ebitda = a.ebitda * (1 - a.downside_pct / 100)
    leverage = a.debt / ebitda
    icr = ebitda / a.cash_interest
    cfads = max(0, ebitda - a.capex - a.cash_taxes)
    dscr = cfads / (a.cash_interest + a.scheduled_principal)
    rows = [
        {"covenant": "Net leverage", "actual": round(leverage, 2), "threshold": a.max_leverage_x, "headroom_pct": round((a.max_leverage_x / leverage - 1) * 100, 2), "status": "Pass" if leverage <= a.max_leverage_x else "Breach"},
        {"covenant": "Interest cover", "actual": round(icr, 2), "threshold": a.min_interest_cover_x, "headroom_pct": round((icr / a.min_interest_cover_x - 1) * 100, 2), "status": "Pass" if icr >= a.min_interest_cover_x else "Breach"},
        {"covenant": "DSCR", "actual": round(dscr, 2), "threshold": a.min_dscr_x, "headroom_pct": round((dscr / a.min_dscr_x - 1) * 100, 2), "status": "Pass" if dscr >= a.min_dscr_x else "Breach"},
        {"covenant": "Minimum liquidity", "actual": a.liquidity, "threshold": a.min_liquidity, "headroom_pct": round((a.liquidity / a.min_liquidity - 1) * 100, 2) if a.min_liquidity else None, "status": "Pass" if a.liquidity >= a.min_liquidity else "Breach"},
    ]
    return _artifact("Covenant headroom", f"{a.downside_pct:.0f}% EBITDA downside", ["covenant", "actual", "threshold", "headroom_pct", "status"], rows,
                     {"breaches": [r["covenant"] for r in rows if r["status"] == "Breach"]})


test_covenant_headroom = StructuredTool.from_function(
    func=_test_covenant_headroom, name="test_covenant_headroom",
    description="Test leverage, interest-cover, DSCR and minimum-liquidity covenant headroom under a downside.", args_schema=CovenantArgs)


class ValuationArgs(BaseModel):
    principal: float = Field(gt=0)
    coupon_pct: float = Field(ge=0)
    remaining_years: int = Field(ge=1, le=30)
    market_yield_pct: float = Field(gt=0)
    annual_pd_pct: float = Field(default=0, ge=0, le=100)
    recovery_pct: float = Field(default=40, ge=0, le=100)
    accrued_interest: float = Field(default=0, ge=0)


def _value_private_debt(**kw) -> str:
    a = ValuationArgs(**kw)
    survival = 1.0
    pv, rows = 0.0, []
    for year in range(1, a.remaining_years + 1):
        opening_survival = survival
        default_prob = opening_survival * a.annual_pd_pct / 100
        survival *= 1 - a.annual_pd_pct / 100
        contractual = a.principal * a.coupon_pct / 100 + (a.principal if year == a.remaining_years else 0)
        expected = contractual * survival + a.principal * a.recovery_pct / 100 * default_prob
        discounted = expected / ((1 + a.market_yield_pct / 100) ** year)
        pv += discounted
        rows.append({"year": year, "survival_pct": round(survival * 100, 2), "expected_cashflow": round(expected, 2), "present_value": round(discounted, 2)})
    clean = pv
    dirty = clean + a.accrued_interest
    return _artifact("Private debt valuation", f"{a.market_yield_pct:.2f}% market yield", ["year", "survival_pct", "expected_cashflow", "present_value"], rows,
                     {"clean_value": round(clean, 2), "dirty_value": round(dirty, 2), "price_pct_par": round(clean / a.principal * 100, 2),
                      "annual_pd_pct": a.annual_pd_pct, "recovery_pct": a.recovery_pct, "synthetic_calibration": True})


value_private_debt = StructuredTool.from_function(func=_value_private_debt, name="value_private_debt",
    description="Value private debt with probability-weighted contractual and recovery cash flows.", args_schema=ValuationArgs)


class WaterfallTranche(BaseModel):
    name: str
    claim: float = Field(gt=0)
    priority: int = Field(ge=1)


class RecoveryArgs(BaseModel):
    enterprise_value: float = Field(ge=0)
    collateral_value: float = Field(default=0, ge=0)
    collateral_haircut_pct: float = Field(default=30, ge=0, le=100)
    enforcement_cost_pct: float = Field(default=5, ge=0, le=100)
    tranches: list[WaterfallTranche] = Field(min_length=1)


def _model_recovery_waterfall(**kw) -> str:
    a = RecoveryArgs(**kw)
    collateral_net = a.collateral_value * (1 - a.collateral_haircut_pct / 100)
    pool = max(a.enterprise_value, collateral_net) * (1 - a.enforcement_cost_pct / 100)
    rows = []
    for t in sorted(a.tranches, key=lambda x: x.priority):
        recovery = min(pool, t.claim)
        pool -= recovery
        rows.append({"tranche": t.name, "priority": t.priority, "claim": t.claim, "recovery": round(recovery, 2),
                     "recovery_pct": round(recovery / t.claim * 100, 2), "lgd_pct": round((1 - recovery / t.claim) * 100, 2)})
    return _artifact("Recovery waterfall", f"Net distributable value {max(a.enterprise_value, collateral_net) * (1-a.enforcement_cost_pct/100):,.0f}",
                     ["tranche", "priority", "claim", "recovery", "recovery_pct", "lgd_pct"], rows,
                     {"residual_value": round(pool, 2), "collateral_net": round(collateral_net, 2)})


model_recovery_waterfall = StructuredTool.from_function(func=_model_recovery_waterfall, name="model_recovery_waterfall",
    description="Allocate stressed enterprise or collateral value through a priority waterfall and calculate facility LGD.", args_schema=RecoveryArgs)


class CollateralPool(BaseModel):
    collateral_type: str
    gross_value: float = Field(ge=0)
    eligible_pct: float = Field(default=100, ge=0, le=100)
    advance_rate_pct: float = Field(default=70, ge=0, le=100)
    reserve: float = Field(default=0, ge=0)


class BorrowingBaseArgs(BaseModel):
    pools: list[CollateralPool] = Field(min_length=1)
    drawn_amount: float = Field(default=0, ge=0)
    commitment: float = Field(gt=0)


def _calculate_borrowing_base(**kw) -> str:
    a = BorrowingBaseArgs(**kw)
    rows, total = [], 0.0
    for p in a.pools:
        eligible = p.gross_value * p.eligible_pct / 100
        availability = max(0, eligible * p.advance_rate_pct / 100 - p.reserve)
        total += availability
        rows.append({"collateral": p.collateral_type, "gross_value": p.gross_value, "eligible_value": round(eligible, 2),
                     "advance_rate_pct": p.advance_rate_pct, "reserve": p.reserve, "availability": round(availability, 2)})
    availability = min(a.commitment, total)
    excess = availability - a.drawn_amount
    return _artifact("Borrowing base", f"Available {availability:,.0f} · excess {excess:,.0f}",
                     ["collateral", "gross_value", "eligible_value", "advance_rate_pct", "reserve", "availability"], rows,
                     {"borrowing_base": round(total, 2), "facility_availability": round(availability, 2), "drawn_amount": a.drawn_amount,
                      "excess_availability": round(excess, 2), "status": "Overdrawn" if excess < 0 else "Compliant"})


calculate_borrowing_base = StructuredTool.from_function(func=_calculate_borrowing_base, name="calculate_borrowing_base",
    description="Calculate ABL or collateral borrowing availability from eligibility, advance rates and reserves.", args_schema=BorrowingBaseArgs)


class MonitorExposure(BaseModel):
    borrower: str
    ead: float = Field(gt=0)
    rating: int = Field(ge=1, le=8)
    prior_rating: int = Field(ge=1, le=8)
    covenant_headroom_pct: float
    liquidity_months: float = Field(ge=0)
    interest_cover_x: float = Field(ge=0)
    pik_pct: float = Field(default=0, ge=0)


class MonitorArgs(BaseModel):
    exposures: list[MonitorExposure] = Field(min_length=1)


def _monitor_credit_portfolio(**kw) -> str:
    a = MonitorArgs(**kw)
    rows = []
    for e in a.exposures:
        triggers = []
        if e.rating > e.prior_rating: triggers.append("downgrade")
        if e.covenant_headroom_pct < 10: triggers.append("low covenant headroom")
        if e.liquidity_months < 6: triggers.append("liquidity")
        if e.interest_cover_x < 1.5: triggers.append("coverage")
        if e.pik_pct > 25: triggers.append("high PIK")
        status = "watch" if triggers else "performing"
        rows.append({"borrower": e.borrower, "ead": e.ead, "rating": e.rating, "migration": e.rating-e.prior_rating,
                     "headroom_pct": e.covenant_headroom_pct, "status": status, "triggers": ", ".join(triggers) or "none"})
    return _artifact("Credit watchlist", f"{sum(r['status']=='watch' for r in rows)} of {len(rows)} exposures on watch",
                     ["borrower", "ead", "rating", "migration", "headroom_pct", "status", "triggers"], rows,
                     {"watch_ead": round(sum(r["ead"] for r in rows if r["status"] == "watch"), 2)})


monitor_credit_portfolio = StructuredTool.from_function(func=_monitor_credit_portfolio, name="monitor_credit_portfolio",
    description="Create a deterministic early-warning watchlist from rating, liquidity, coverage, covenant and PIK triggers.", args_schema=MonitorArgs)


class WorkoutArgs(BaseModel):
    claim: float = Field(gt=0)
    going_concern_recovery_pct: float = Field(ge=0, le=100)
    liquidation_recovery_pct: float = Field(ge=0, le=100)
    amendment_recovery_pct: float = Field(ge=0, le=100)
    amendment_success_pct: float = Field(default=65, ge=0, le=100)
    months_to_enforcement: int = Field(default=18, ge=0, le=120)
    discount_rate_pct: float = Field(default=15, ge=0)


def _compare_workout_options(**kw) -> str:
    a = WorkoutArgs(**kw)
    scenarios = [
        ("Amend and extend", a.amendment_recovery_pct, a.amendment_success_pct, 12),
        ("Going-concern sale", a.going_concern_recovery_pct, 75, a.months_to_enforcement),
        ("Liquidation", a.liquidation_recovery_pct, 95, a.months_to_enforcement + 6),
    ]
    rows = []
    for name, recovery, probability, months in scenarios:
        gross = a.claim * recovery / 100
        expected = gross * probability / 100
        pv = expected / ((1 + a.discount_rate_pct / 100) ** (months / 12))
        rows.append({"option": name, "recovery_pct": recovery, "success_pct": probability, "months": months, "expected_pv": round(pv, 2)})
    rows.sort(key=lambda r: r["expected_pv"], reverse=True)
    return _artifact("Workout options", f"Preferred: {rows[0]['option']}", ["option", "recovery_pct", "success_pct", "months", "expected_pv"], rows,
                     {"preferred_option": rows[0]["option"], "synthetic_calibration": True})


compare_workout_options = StructuredTool.from_function(func=_compare_workout_options, name="compare_workout_options",
    description="Compare amend-and-extend, going-concern sale and liquidation on probability- and time-adjusted recovery.", args_schema=WorkoutArgs)


class PortfolioExposure(BaseModel):
    borrower: str
    strategy: str
    sector: str
    sponsor: str
    ead: float = Field(gt=0)
    yield_pct: float = Field(ge=0)
    pd_pct: float = Field(ge=0, le=100)
    lgd_pct: float = Field(ge=0, le=100)
    maturity_year: int


class PortfolioArgs(BaseModel):
    exposures: list[PortfolioExposure] = Field(min_length=1)
    max_single_name_pct: float = Field(default=10, gt=0, le=100)
    max_sector_pct: float = Field(default=25, gt=0, le=100)


def _construct_credit_portfolio(**kw) -> str:
    a = PortfolioArgs(**kw)
    total = sum(e.ead for e in a.exposures)
    sector_totals: dict[str, float] = {}
    rows = []
    for e in a.exposures:
        sector_totals[e.sector] = sector_totals.get(e.sector, 0) + e.ead
        loss_pct = e.pd_pct * e.lgd_pct / 100
        weight = e.ead / total * 100
        rows.append({"borrower": e.borrower, "strategy": e.strategy, "sector": e.sector, "weight_pct": round(weight, 2),
                     "yield_pct": e.yield_pct, "expected_loss_pct": round(loss_pct, 3), "risk_adjusted_yield_pct": round(e.yield_pct-loss_pct, 3),
                     "limit_status": "Breach" if weight > a.max_single_name_pct else "Pass"})
    sector_breaches = {k: round(v/total*100, 2) for k, v in sector_totals.items() if v/total*100 > a.max_sector_pct}
    return _artifact("Credit portfolio construction", f"{len(rows)} exposures · {total:,.0f} EAD",
                     ["borrower", "strategy", "sector", "weight_pct", "yield_pct", "expected_loss_pct", "risk_adjusted_yield_pct", "limit_status"], rows,
                     {"sector_breaches": sector_breaches, "weighted_yield_pct": round(sum(e.ead*e.yield_pct for e in a.exposures)/total, 3),
                      "synthetic_calibration": True})


construct_credit_portfolio = StructuredTool.from_function(func=_construct_credit_portfolio, name="construct_credit_portfolio",
    description="Analyze risk-adjusted yield and borrower/sector concentration for a private-credit portfolio.", args_schema=PortfolioArgs)
