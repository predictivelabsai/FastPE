"""Reproducible synthetic private-credit portfolio fixtures.

These records exercise product workflows; they are not empirical calibration.
Venture debt is intentionally excluded.
"""

from __future__ import annotations

import random
from datetime import date

from dateutil.relativedelta import relativedelta


STRATEGIES = (
    "direct_lending", "abl", "real_estate", "infrastructure",
    "fund_finance", "specialty_finance", "distressed",
)

FACILITY_TYPES = {
    "direct_lending": ("senior_term", "unitranche", "second_lien", "mezzanine"),
    "abl": ("revolver", "receivables_facility"),
    "real_estate": ("investment_loan", "development_loan"),
    "infrastructure": ("project_finance", "holdco_loan"),
    "fund_finance": ("subscription_line", "nav_facility"),
    "specialty_finance": ("warehouse_facility", "forward_flow"),
    "distressed": ("rescue_finance", "super_senior"),
}


def generate_for_companies(cos_with_ids: list[tuple[int, dict]], seed: int = 42) -> list[dict]:
    rng = random.Random(seed + 1701)
    rows = []
    today = date.today()
    for i, (company_id, co) in enumerate(cos_with_ids):
        strategy = STRATEGIES[i % len(STRATEGIES)]
        ebitda = max(float(co.get("ebitda_ltm") or 2_000_000), 500_000)
        leverage = rng.uniform(2.5, 6.5)
        commitment = round(ebitda * leverage, -3)
        drawn = commitment * rng.uniform(0.70, 1.0)
        grade = rng.randint(2, 7)
        pd_map = {1: .25, 2: .75, 3: 1.5, 4: 3.0, 5: 6.0, 6: 12.0, 7: 25.0, 8: 50.0}
        lgd = rng.uniform(20, 65)
        spread = rng.choice([425, 500, 575, 650, 750, 900, 1100])
        term = rng.choice([3, 4, 5, 6, 7])
        collateral_type = {
            "abl": "receivables_and_inventory", "real_estate": "real_estate",
            "infrastructure": "project_assets", "fund_finance": "fund_interests",
            "specialty_finance": "financial_assets", "distressed": "all_assets",
        }.get(strategy, "enterprise_value")
        rows.append({
            "company_id": company_id, "name": f"{co['name']} — Synthetic Credit Facility",
            "strategy": strategy, "facility_type": rng.choice(FACILITY_TYPES[strategy]),
            "currency": rng.choice(["EUR", "EUR", "GBP", "USD"]),
            "commitment": commitment, "drawn_amount": round(drawn, 2),
            "base_rate_pct": rng.choice([2.5, 3.0, 3.5, 4.0]), "spread_bps": spread,
            "floor_pct": rng.choice([0.0, 1.0, 2.0]), "pik_interest_pct": rng.choice([0, 0, 0, 2, 4]),
            "oid_pct": rng.choice([97.5, 98.0, 99.0, 100.0]), "upfront_fee_pct": rng.choice([0.5, 1.0, 1.5, 2.0]),
            "amortization_pct": rng.choice([0, 1, 2.5, 5]), "maturity_date": today + relativedelta(years=term),
            "lien": rng.choice(["first_lien", "first_lien", "second_lien", "senior_secured"]),
            "obligor_grade": str(grade), "pd_pct": pd_map[grade], "lgd_pct": round(lgd, 2),
            "ebitda": ebitda, "collateral_type": collateral_type,
            "collateral_value": round(commitment * rng.uniform(1.1, 2.2), 2),
            "advance_rate_pct": rng.choice([50, 60, 70, 80, 85]),
            "covenant_type": "max_leverage" if strategy not in ("real_estate", "infrastructure") else ("max_ltv" if strategy == "real_estate" else "min_dscr"),
            "covenant_threshold": round(rng.uniform(4.5, 6.5), 2) if strategy not in ("real_estate", "infrastructure") else (70 if strategy == "real_estate" else 1.25),
            "covenant_direction": "maximum" if strategy != "infrastructure" else "minimum",
            "leverage_x": round(drawn / ebitda, 2), "interest_cover_x": round(rng.uniform(1.1, 3.5), 2),
            "dscr_x": round(rng.uniform(1.0, 2.0), 2), "headroom_pct": round(rng.uniform(-8, 35), 2),
            "liquidity": round(ebitda * rng.uniform(.25, 1.5), 2),
            "revenue_variance_pct": round(rng.uniform(-20, 12), 2), "ebitda_variance_pct": round(rng.uniform(-30, 10), 2),
        })
    return rows
