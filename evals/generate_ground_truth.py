"""Generate ground-truth CSV files for PE Hero agent evaluation.

Produces:
  ground_truth/routing_eval.csv   — query → expected agent slug (prefix, keyword, free-form)
  ground_truth/response_eval.csv  — query → expected patterns / keywords in response

Usage:
    python -m evals.generate_ground_truth
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from agents.registry import AGENTS

GT_DIR = Path(__file__).resolve().parent / "ground_truth"


def _routing_rows() -> list[dict]:
    """Build routing eval rows from registry specs + manual cases."""
    rows: list[dict] = []

    for spec in AGENTS:
        prefix = spec.prefix.lower()
        # --- Prefix-routed cases (deterministic) ---
        for prompt in spec.example_prompts[:2]:
            if prompt.lower().startswith(prefix):
                rows.append({
                    "question": prompt,
                    "expected_slug": spec.slug,
                    "route_type": "prefix",
                    "category": spec.category,
                    "agent_name": spec.name,
                })

        # --- Free-form cases (from remaining example_prompts) ---
        for prompt in spec.example_prompts[1:]:
            if not prompt.lower().startswith(prefix):
                rows.append({
                    "question": prompt,
                    "expected_slug": spec.slug,
                    "route_type": "free_form",
                    "category": spec.category,
                    "agent_name": spec.name,
                })

    # --- Manual keyword-routed cases ---
    manual = [
        ("What logistics deals surfaced this week?", "market_scanner", "keyword"),
        ("Should we pursue Baltic Transline?", "deal_triage", "keyword"),
        ("Find trading comps for a veterinary clinic chain", "comp_finder", "keyword"),
        ("Which companies in our pipeline are most likely to sell?", "seller_intent", "keyword"),
        ("Draft an intro email to the founder of DR VET", "outreach_email", "keyword"),
        ("Plan a 5-touch outreach for Baltic transline founder", "outreach_sequencer", "keyword"),
        ("Draft an LOI for Kardiolita at €85M EV", "loi_writer", "keyword"),
        ("Parse the cap table for Kardiolita", "rent_roll_parser", "keyword"),
        ("Normalize the LTM P&L for DR VET", "t12_normalizer", "keyword"),
        ("Build a 5-year LBO model for Northway", "pro_forma_builder", "keyword"),
        ("Size a unitranche facility for €15M EBITDA", "debt_stack_modeler", "keyword"),
        ("What are the IRR and MOIC at 8x exit?", "return_metrics", "keyword"),
        ("Check the data room for missing documents", "doc_room_auditor", "keyword"),
        ("Abstract the change-of-control clauses across MSAs", "lease_abstractor", "keyword"),
        ("Any regulatory risks for a Lithuanian healthcare target?", "title_zoning", "keyword"),
        ("Review the operational diligence findings", "physical_condition", "keyword"),
        ("Flag ESG and environmental compliance risks", "environmental_risk", "keyword"),
        ("Write an IC memo for the Kardiolita investment", "investor_memo", "keyword"),
        ("Create a 1-page deal teaser for Baltic Transline", "deal_teaser", "keyword"),
        ("Draft a quarterly LP update letter", "lp_update", "keyword"),
        ("Show me the fundraising CRM pipeline status", "fundraising_crm", "keyword"),
        ("Where is pricing below market across the portfolio?", "rent_optimization", "keyword"),
        ("What's driving the EBITDA variance this quarter?", "opex_variance", "keyword"),
        ("Rank value creation initiatives for DR VET", "capex_prioritizer", "keyword"),
        ("Which customers are at highest churn risk?", "tenant_churn", "keyword"),
        # Edge cases — ambiguous routing
        ("Tell me about DR VET", "deal_triage", "free_form"),
        ("What should I know before our next board meeting?", "deal_triage", "free_form"),
        ("Help me with this deal", "deal_triage", "free_form"),
    ]
    from agents.registry import AGENTS_BY_SLUG
    for q, slug, rtype in manual:
        spec = AGENTS_BY_SLUG[slug]
        rows.append({
            "question": q,
            "expected_slug": slug,
            "route_type": rtype,
            "category": spec.category,
            "agent_name": spec.name,
        })

    return rows


def _response_rows() -> list[dict]:
    """Build response eval rows — first example_prompt per agent with expected patterns."""
    rows: list[dict] = []

    response_hints: dict[str, dict] = {
        "market_scanner": {
            "must_contain": "healthcare|clinic|deal|company|target",
            "must_not_contain": "I don't know|I cannot",
            "quality_check": "Returns structured deal opportunities with company names",
        },
        "deal_triage": {
            "must_contain": "revenue|EBITDA|fit|proceed|pass|investment criteria",
            "must_not_contain": "I don't know",
            "quality_check": "Provides go/no-go recommendation with rationale",
        },
        "comp_finder": {
            "must_contain": "EV/EBITDA|multiple|transaction|comparable",
            "must_not_contain": "I don't know",
            "quality_check": "Returns comparable transactions with multiples",
        },
        "pro_forma_builder": {
            "must_contain": "IRR|MOIC|EBITDA|year|exit",
            "must_not_contain": "I don't know",
            "quality_check": "Builds a multi-year financial projection with returns",
        },
        "debt_stack_modeler": {
            "must_contain": "senior|debt|leverage|DSCR|facility",
            "must_not_contain": "I don't know",
            "quality_check": "Sizes debt tranches with coverage ratios",
        },
        "return_metrics": {
            "must_contain": "IRR|MOIC|return|equity",
            "must_not_contain": "I don't know",
            "quality_check": "Calculates investment returns with sensitivity analysis",
        },
        "investor_memo": {
            "must_contain": "investment|thesis|risk|recommendation",
            "must_not_contain": "I don't know",
            "quality_check": "Produces a structured IC memo with sections",
        },
        "loi_writer": {
            "must_contain": "LOI|letter|intent|enterprise value|exclusivity",
            "must_not_contain": "I don't know",
            "quality_check": "Drafts a formal LOI with standard terms",
        },
        "rent_roll_parser": {
            "must_contain": "ownership|shares|cap table|dilut",
            "must_not_contain": "I don't know",
            "quality_check": "Parses and summarizes cap table data",
        },
        "t12_normalizer": {
            "must_contain": "EBITDA|add-back|adjusted|revenue",
            "must_not_contain": "I don't know",
            "quality_check": "Normalizes financials with standard add-backs",
        },
        "doc_room_auditor": {
            "must_contain": "document|data room|missing|complete",
            "must_not_contain": "I don't know",
            "quality_check": "Audits VDR completeness with checklist",
        },
        "lease_abstractor": {
            "must_contain": "contract|clause|term|provision",
            "must_not_contain": "I don't know",
            "quality_check": "Abstracts key contract terms",
        },
        "environmental_risk": {
            "must_contain": "ESG|environmental|risk|compliance",
            "must_not_contain": "I don't know",
            "quality_check": "Flags ESG and compliance risks",
        },
        "deal_teaser": {
            "must_contain": "teaser|opportunity|highlights|overview",
            "must_not_contain": "I don't know",
            "quality_check": "Creates a 1-page deal teaser",
        },
        "lp_update": {
            "must_contain": "portfolio|fund|quarter|performance",
            "must_not_contain": "I don't know",
            "quality_check": "Generates LP update letter with fund metrics",
        },
        "rent_optimization": {
            "must_contain": "pricing|below market|increase|optimization",
            "must_not_contain": "I don't know",
            "quality_check": "Identifies pricing optimization opportunities",
        },
        "opex_variance": {
            "must_contain": "variance|budget|over|under|EBITDA",
            "must_not_contain": "I don't know",
            "quality_check": "Explains EBITDA variance drivers",
        },
        "capex_prioritizer": {
            "must_contain": "value creation|initiative|priority|ROI",
            "must_not_contain": "I don't know",
            "quality_check": "Ranks value creation initiatives",
        },
        "tenant_churn": {
            "must_contain": "churn|risk|retention|customer",
            "must_not_contain": "I don't know",
            "quality_check": "Predicts customer churn with risk factors",
        },
    }

    for spec in AGENTS:
        prompt = spec.example_prompts[0] if spec.example_prompts else None
        if not prompt:
            continue
        hints = response_hints.get(spec.slug, {
            "must_contain": "",
            "must_not_contain": "I don't know|I cannot",
            "quality_check": f"Agent {spec.name} provides a relevant, structured response",
        })
        rows.append({
            "question": prompt,
            "expected_slug": spec.slug,
            "agent_name": spec.name,
            "category": spec.category,
            "must_contain": hints.get("must_contain", ""),
            "must_not_contain": hints.get("must_not_contain", ""),
            "quality_check": hints.get("quality_check", ""),
        })

    return rows


def write_csv(rows: list[dict], path: Path):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"  {path.name}: {len(rows)} rows")


def main():
    print("Generating ground truth ...")

    routing_rows = _routing_rows()
    write_csv(routing_rows, GT_DIR / "routing_eval.csv")

    response_rows = _response_rows()
    write_csv(response_rows, GT_DIR / "response_eval.csv")

    meta = {
        "routing_cases": len(routing_rows),
        "response_cases": len(response_rows),
        "agents": len(AGENTS),
    }
    (GT_DIR / "generation_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"  generation_meta.json: {json.dumps(meta)}")
    print("Done.")


if __name__ == "__main__":
    main()
