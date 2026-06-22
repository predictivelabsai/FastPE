"""Triage scoring for PE deal prioritisation.

Weighted model (cxhub-inspired):
  40% estimated impact   — revenue scale + margin quality
  30% strategic fit      — sector attractiveness + growth
  20% feasibility        — seller intent + deal stage readiness
  10% urgency            — how far along the deal is

Each dimension scored 1.0–5.0, then weighted to a single 1.0–5.0 total.
"""

from __future__ import annotations

WEIGHTS = {
    "impact":       0.40,
    "strategic_fit": 0.30,
    "feasibility":  0.20,
    "urgency":      0.10,
}

SECTOR_ATTRACTIVENESS = {
    "software": 4.5,
    "healthcare": 4.0,
    "financial_services": 3.8,
    "business_services": 3.5,
    "consumer": 3.2,
    "industrials": 3.0,
}

STAGE_URGENCY = {
    "signed": 5.0, "ic": 4.8, "diligence": 4.5, "loi": 4.0,
    "screened": 3.0, "sourced": 2.0, "held": 2.5, "closed": 1.5,
    "exited": 1.0, "passed": 1.0,
}

INTENT_FEASIBILITY = {"hot": 5.0, "warm": 3.5, "cold": 2.0}


def _clamp(v: float) -> float:
    return max(1.0, min(5.0, v))


def triage_score(
    revenue: float = 0,
    ebitda_margin: float = 0,
    growth_rate: float = 0,
    sector: str = "",
    seller_intent: str = "",
    deal_stage: str = "sourced",
) -> tuple[float, str]:
    """Return (weighted_score, priority_band)."""
    rev_m = revenue / 1_000_000 if revenue else 0
    impact = _clamp(1.0 + min(rev_m / 50, 2.0) + min(ebitda_margin / 10, 2.0))

    sector_base = SECTOR_ATTRACTIVENESS.get(sector, 3.0)
    growth_bonus = min(growth_rate / 10, 1.5) if growth_rate > 0 else 0
    strategic_fit = _clamp(sector_base * 0.7 + growth_bonus + 1.0)

    intent_base = INTENT_FEASIBILITY.get(seller_intent, 2.5)
    stage_mod = 0.5 if deal_stage in ("diligence", "ic", "signed") else 0
    feasibility = _clamp(intent_base + stage_mod)

    urgency = STAGE_URGENCY.get(deal_stage, 2.0)

    weighted = sum(
        WEIGHTS[k] * v for k, v in [
            ("impact", impact),
            ("strategic_fit", strategic_fit),
            ("feasibility", feasibility),
            ("urgency", urgency),
        ]
    )
    weighted = round(weighted, 2)
    band = priority_band(weighted)
    return weighted, band


def priority_band(weighted: float) -> str:
    if weighted >= 4.0:
        return "High"
    if weighted >= 3.0:
        return "Medium"
    return "Low"
