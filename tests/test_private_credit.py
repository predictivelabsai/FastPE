"""Private-credit calculation, routing, registry, and synthetic-data coverage."""

from __future__ import annotations

import json

from agents.registry import AGENTS, AGENTS_BY_SLUG
from agents.router import route
from synthetic.credit import STRATEGIES, generate_for_companies
from tools.credit import (
    calculate_borrowing_base,
    compare_workout_options,
    construct_credit_portfolio,
    model_debt_cashflows,
    model_default_risk,
    model_recovery_waterfall,
    monitor_credit_portfolio,
    test_covenant_headroom as covenant_tool,
    value_private_debt,
)


def _payload(result: str) -> dict:
    assert result.startswith("__ARTIFACT__")
    return json.loads(result.removeprefix("__ARTIFACT__"))


def test_all_agents_have_strategy_labels_and_credit_squad_is_complete():
    assert all(a.asset_class in {"equity", "credit", "both"} for a in AGENTS)
    credit = {a.slug for a in AGENTS if a.asset_class == "credit"}
    assert credit == {
        "credit_opportunity_screener", "default_risk_modeler", "debt_cashflow_pricing",
        "covenant_headroom", "private_debt_valuation", "recovery_waterfall",
        "abl_collateral", "loan_terms_extractor", "credit_memo_writer",
        "credit_portfolio_monitor", "restructuring_workout", "credit_portfolio_constructor",
    }


def test_private_credit_prefix_and_natural_language_routing():
    cases = {
        "default: calculate PD and LGD": "default_risk_modeler",
        "debtcf: model cash and PIK interest": "debt_cashflow_pricing",
        "covenant: show downside headroom": "covenant_headroom",
        "loanval: mark this loan": "private_debt_valuation",
        "recovery: run the lien waterfall": "recovery_waterfall",
        "abl: calculate the borrowing base": "abl_collateral",
        "terms: extract the agreement": "loan_terms_extractor",
        "creditmemo: write the lender IC paper": "credit_memo_writer",
        "watch: show the watchlist": "credit_portfolio_monitor",
        "workout: compare enforcement": "restructuring_workout",
        "credport: test concentrations": "credit_portfolio_constructor",
        "What is the probability of default and expected loss?": "default_risk_modeler",
        "Calculate ABL advance rates and borrowing base": "abl_collateral",
        "Prepare a credit memo for the unitranche": "credit_memo_writer",
    }
    for message, expected in cases.items():
        assert route(message) == expected


def test_default_risk_is_explicitly_synthetic_and_reconciles():
    result = json.loads(model_default_risk.invoke({
        "leverage_x": 5.0, "interest_cover_x": 1.6, "revenue_growth_pct": -5,
        "recurring_revenue_pct": 55, "sponsor_support": "moderate",
        "collateral_coverage_x": 1.2, "ead": 10_000_000,
    }))
    assert result["synthetic_calibration"] is True
    assert result["expected_loss"] == round(10_000_000 * result["pd_pct"] / 100 * result["facility_lgd_pct"] / 100, 2)


def test_debt_cashflows_amortize_and_return_lender_irr():
    data = _payload(model_debt_cashflows.invoke({
        "principal": 10_000_000, "term_years": 5, "base_rate_pct": 3,
        "spread_bps": 650, "pik_interest_pct": 2, "amortization_pct": 2,
        "oid_pct": 98, "upfront_fee_pct": 1,
    }))
    assert data["rows"][-1]["closing_balance"] == 0
    assert data["summary"]["lender_irr_pct"] > 0


def test_covenant_breach_valuation_recovery_and_borrowing_base():
    cov = _payload(covenant_tool.invoke({
        "debt": 55, "ebitda": 10, "cash_interest": 5, "scheduled_principal": 2,
        "max_leverage_x": 5.5, "min_interest_cover_x": 1.75, "min_dscr_x": 1.2,
        "downside_pct": 20,
    }))
    assert cov["summary"]["breaches"]
    val = _payload(value_private_debt.invoke({
        "principal": 100, "coupon_pct": 9, "remaining_years": 5,
        "market_yield_pct": 12, "annual_pd_pct": 4, "recovery_pct": 40,
    }))
    assert 0 < val["summary"]["price_pct_par"] < 100
    rec = _payload(model_recovery_waterfall.invoke({
        "enterprise_value": 80, "collateral_value": 70,
        "tranches": [{"name": "First lien", "claim": 60, "priority": 1},
                     {"name": "Second lien", "claim": 40, "priority": 2}],
    }))
    assert rec["rows"][0]["recovery_pct"] >= rec["rows"][1]["recovery_pct"]
    abl = _payload(calculate_borrowing_base.invoke({
        "commitment": 20, "drawn_amount": 12,
        "pools": [{"collateral_type": "receivables", "gross_value": 20, "eligible_pct": 90, "advance_rate_pct": 80}],
    }))
    assert abl["summary"]["status"] == "Compliant"


def test_monitor_workout_and_portfolio_tools():
    watch = _payload(monitor_credit_portfolio.invoke({"exposures": [{
        "borrower": "Example", "ead": 10, "rating": 6, "prior_rating": 4,
        "covenant_headroom_pct": 5, "liquidity_months": 3, "interest_cover_x": 1.2, "pik_pct": 30,
    }]}))
    assert watch["rows"][0]["status"] == "watch"
    workout = _payload(compare_workout_options.invoke({
        "claim": 100, "going_concern_recovery_pct": 60, "liquidation_recovery_pct": 35,
        "amendment_recovery_pct": 80,
    }))
    assert workout["summary"]["preferred_option"]
    portfolio = _payload(construct_credit_portfolio.invoke({
        "max_single_name_pct": 60, "max_sector_pct": 60,
        "exposures": [
            {"borrower": "A", "strategy": "direct_lending", "sector": "healthcare", "sponsor": "S1", "ead": 60, "yield_pct": 10, "pd_pct": 3, "lgd_pct": 40, "maturity_year": 2030},
            {"borrower": "B", "strategy": "real_estate", "sector": "property", "sponsor": "S2", "ead": 40, "yield_pct": 9, "pd_pct": 4, "lgd_pct": 45, "maturity_year": 2029},
        ],
    }))
    assert portfolio["summary"]["weighted_yield_pct"] == 9.6


def test_synthetic_generator_covers_every_included_strategy_and_is_reproducible():
    companies = [(i + 1, {"name": f"Borrower {i}", "ebitda_ltm": 2_000_000 + i * 10_000}) for i in range(14)]
    first = generate_for_companies(companies, seed=77)
    second = generate_for_companies(companies, seed=77)
    assert first == second
    assert {row["strategy"] for row in first} == set(STRATEGIES)
    assert all("venture" not in row["strategy"] for row in first)
    assert all(row["pd_pct"] > 0 and row["lgd_pct"] > 0 for row in first)
