"""Capital / LP tools: IC memo briefs, LP CRM, fund portfolio snapshot."""

from __future__ import annotations

import json
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from db import fetch_all, fetch_one


class CompanyArgs(BaseModel):
    slug_or_id: str = Field(description="Company slug or id.")


def _resolve_cid(slug_or_id):
    try:
        return int(slug_or_id)
    except (TypeError, ValueError):
        row = fetch_one("SELECT id FROM pehero.companies WHERE slug = %s", (slug_or_id,))
        return row["id"] if row else None


def _deal_brief(slug_or_id: str) -> str:
    """Compact structured dump of everything the memo/teaser writers need."""
    cid = _resolve_cid(slug_or_id)
    if not cid:
        return "Company not found."
    co = fetch_one("SELECT * FROM pehero.companies WHERE id = %s", (cid,))
    ltm = fetch_all(
        "SELECT revenue, ebitda, adj_ebitda FROM pehero.financials "
        "WHERE company_id = %s ORDER BY month DESC LIMIT 12",
        (cid,),
    )
    ltm_rev = sum(float(r["revenue"] or 0) for r in ltm)
    ltm_ebitda = sum(float(r["ebitda"] or 0) for r in ltm)
    ltm_adj = sum(float(r["adj_ebitda"] or 0) for r in ltm)

    pf = fetch_one(
        "SELECT assumptions, returns FROM pehero.lbo_models "
        "WHERE company_id = %s ORDER BY id DESC LIMIT 1",
        (cid,),
    )
    debt = fetch_one(
        "SELECT total_debt, total_leverage, dscr, tranches FROM pehero.debt_stacks "
        "WHERE company_id = %s ORDER BY id DESC LIMIT 1",
        (cid,),
    )
    comps = fetch_all(
        "SELECT avg(ev_ebitda) as avg_ebitda, avg(ev_revenue) as avg_rev "
        "FROM pehero.transaction_comps WHERE sector = %s",
        (co["sector"],),
    )
    brief = {
        "company": {
            "name": co["name"], "hq_city": co["hq_city"], "hq_state": co["hq_state"],
            "country": co["country"], "sector": co["sector"], "sub_sector": co["sub_sector"],
            "employees": co["employees"], "founded_year": co["founded_year"],
            "ownership": co["ownership"], "deal_stage": co["deal_stage"],
            "deal_type": co["deal_type"],
            "enterprise_value": float(co["enterprise_value"]) if co["enterprise_value"] else None,
            "ask_multiple": float(co["ask_multiple"]) if co["ask_multiple"] else None,
            "description": co["description"],
        },
        "ltm": {
            "revenue": round(ltm_rev, 2),
            "ebitda": round(ltm_ebitda, 2),
            "adj_ebitda": round(ltm_adj, 2),
            "adj_ebitda_margin_pct": round(100 * ltm_adj / max(1, ltm_rev), 2) if ltm_rev else None,
        },
        "lbo_model": {
            "assumptions": pf["assumptions"] if pf else None,
            "returns": pf["returns"] if pf else None,
        },
        "debt_stack": {
            "total_debt": float(debt["total_debt"]) if debt and debt["total_debt"] else None,
            "total_leverage_x": float(debt["total_leverage"]) if debt and debt["total_leverage"] else None,
            "dscr": float(debt["dscr"]) if debt and debt["dscr"] else None,
            "tranches": debt["tranches"] if debt else None,
        },
        "comps": {
            "avg_ev_ebitda": float(comps[0]["avg_ebitda"]) if comps and comps[0]["avg_ebitda"] else None,
            "avg_ev_revenue": float(comps[0]["avg_rev"]) if comps and comps[0]["avg_rev"] else None,
        },
    }
    return json.dumps(brief, default=str)


deal_brief = StructuredTool.from_function(
    func=_deal_brief,
    name="deal_brief",
    description="Pull a compact structured dossier about a company — attributes, LTM financials, LBO model, debt stack, comps — for IC memo / teaser writers to summarize.",
    args_schema=CompanyArgs,
)


class CRMArgs(BaseModel):
    stage: Optional[str] = Field(default=None, description="cold | qualified | meeting | dd | committed | closed | passed")
    focus: Optional[str] = Field(default=None, description="buyout | growth | special_sits | multi_strategy")
    lp_type: Optional[str] = Field(default=None, description="pension | endowment | fof | family_office | sovereign | insurance | hnw")
    min_check: Optional[float] = Field(default=None)
    days_since_touch: Optional[int] = Field(default=None, description="Filter to LPs not touched in N days.")
    limit: int = Field(default=15, ge=1, le=50)


def _crm_lookup(**kw) -> str:
    args = CRMArgs(**kw)
    sql = ["SELECT name, firm, lp_type, email, commitment_size, stage, focus, geography, aum, last_touch, notes "
           "FROM pehero.investor_crm WHERE TRUE"]
    params: list = []
    if args.stage:
        sql.append("AND stage = %s"); params.append(args.stage)
    if args.focus:
        sql.append("AND focus = %s"); params.append(args.focus)
    if args.lp_type:
        sql.append("AND lp_type = %s"); params.append(args.lp_type)
    if args.min_check:
        sql.append("AND commitment_size >= %s"); params.append(args.min_check)
    if args.days_since_touch:
        sql.append("AND last_touch < now() - (%s || ' days')::interval"); params.append(args.days_since_touch)
    sql.append("ORDER BY commitment_size DESC NULLS LAST, last_touch DESC NULLS LAST LIMIT %s")
    params.append(args.limit)
    rows = fetch_all(" ".join(sql), tuple(params))
    if not rows:
        return "No LPs match."
    rows2 = [{**r,
              "commitment_size": float(r["commitment_size"]) if r["commitment_size"] else None,
              "aum": float(r["aum"]) if r["aum"] else None,
              "last_touch": str(r["last_touch"]) if r["last_touch"] else None}
             for r in rows]
    return "__ARTIFACT__" + json.dumps({
        "kind": "table",
        "title": "LP shortlist",
        "columns": ["name", "firm", "lp_type", "stage", "focus", "commitment_size", "last_touch"],
        "rows": rows2,
        "summary": {"count": len(rows2)},
    }, default=str)


rank_lps = StructuredTool.from_function(
    func=_crm_lookup,
    name="rank_lps",
    description="Filter + rank the LP CRM by stage, focus, LP type, min commitment size, and days-since-last-touch.",
    args_schema=CRMArgs,
)
# Back-compat alias
crm_lookup = rank_lps


def _portfolio_snapshot() -> str:
    """For LP updates: portfolio by sector, aggregate revenue / EBITDA, deals closed, weighted performance."""
    rows = fetch_all(
        "SELECT sector, count(*) as n, "
        "sum(revenue_ltm)::numeric as total_rev, sum(ebitda_ltm)::numeric as total_ebitda, "
        "avg(growth_rate) as avg_growth "
        "FROM pehero.companies "
        "WHERE deal_stage IN ('held','closed') "
        "GROUP BY sector ORDER BY sector"
    )
    rows2 = [{"sector": r["sector"], "companies": r["n"],
              "total_revenue_ltm": float(r["total_rev"]) if r["total_rev"] else None,
              "total_ebitda_ltm": float(r["total_ebitda"]) if r["total_ebitda"] else None,
              "avg_growth_pct": round(float(r["avg_growth"]), 1) if r["avg_growth"] else None}
             for r in rows]
    return "__ARTIFACT__" + json.dumps({
        "kind": "table",
        "title": "Portfolio snapshot",
        "columns": ["sector", "companies", "total_revenue_ltm", "total_ebitda_ltm", "avg_growth_pct"],
        "rows": rows2,
    })


portfolio_snapshot = StructuredTool.from_function(
    func=_portfolio_snapshot,
    name="portfolio_snapshot",
    description="Portfolio-wide snapshot by sector — company count, aggregate LTM revenue / EBITDA, average growth.",
)
