"""Load Lithuanian company data from data/lt_companies.json into PEHero DB.

Replaces all synthetic company/financial data with real Lithuanian companies.

Usage:
    python -m scripts.load_lt_data              # load
    python -m scripts.load_lt_data --dry-run    # preview, don't write
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import date
from pathlib import Path

from db import connect

log = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "lt_companies.json"

TRUNCATE_TABLES = [
    "pehero.agent_invocations",
    "pehero.dd_findings",
    "pehero.portfolio_kpis",
    "pehero.market_signals",
    "pehero.investor_crm",
    "pehero.debt_stacks",
    "pehero.lbo_models",
    "pehero.trading_comps",
    "pehero.transaction_comps",
    "pehero.contracts",
    "pehero.financials",
    "pehero.cap_tables",
    "pehero.companies",
]

EV_REVENUE_MULTIPLES = {
    "healthcare": 2.5,
    "business_services": 1.8,
    "financial_services": 3.0,
    "industrials": 1.2,
}


def _parse_euros(text: str) -> float | None:
    if not text:
        return None
    m = re.search(r"([-\d\s]+)\s*€", text.replace(" ", " "))
    if not m:
        return None
    cleaned = m.group(1).replace(" ", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_int(text: str) -> int | None:
    m = re.search(r"(\d[\d\s]*)", text.replace(" ", " "))
    if not m:
        return None
    try:
        return int(m.group(1).replace(" ", ""))
    except ValueError:
        return None


def _parse_year_from_age(age_text: str) -> int | None:
    m = re.search(r"(\d+)\s*year", age_text)
    if m:
        return date.today().year - int(m.group(1))
    return None


def _parse_city(address: str) -> str | None:
    if not address:
        return None
    parts = [p.strip() for p in address.split(",")]
    for p in reversed(parts):
        cleaned = re.sub(r"LT-\d+\s*", "", p).strip()
        if cleaned and not cleaned[0].isdigit() and len(cleaned) > 2:
            return cleaned
    return None


def _make_slug(raw_slug: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", raw_slug.lower()).strip("_")[:60]


def _transform_company(raw: dict) -> dict | None:
    """Transform a scraped company dict into a pehero.companies row."""
    name = raw.get("name", "").strip()
    if not name or len(name) < 2:
        return None

    slug = _make_slug(raw.get("slug", name))
    city = _parse_city(raw.get("address", ""))
    founded = _parse_year_from_age(raw.get("company_age", ""))
    employees = _parse_int(raw.get("employees_text", ""))
    revenue = _parse_euros(raw.get("sales_revenue", ""))
    net_profit = _parse_euros(raw.get("net_profit", ""))

    # Try to get revenue/profit from financials if headline missing
    financials = raw.get("financials", [])
    if (not revenue) and financials:
        latest = max(financials, key=lambda f: f.get("year", 0))
        revenue = latest.get("sales_revenue")
        net_profit = net_profit or latest.get("net_profit")

    # Compute growth rate from 2-year financials
    growth_rate = None
    if len(financials) >= 2:
        sorted_fin = sorted(financials, key=lambda f: f.get("year", 0))
        for i in range(len(sorted_fin) - 1, 0, -1):
            r_new = sorted_fin[i].get("sales_revenue")
            r_old = sorted_fin[i - 1].get("sales_revenue")
            if r_new and r_old and r_old > 0:
                growth_rate = round(max(-999, min(999, (r_new / r_old - 1) * 100)), 1)
                break

    # EBITDA proxy: net profit + ~10% of revenue (rough D&A estimate)
    ebitda = None
    if net_profit is not None and revenue and revenue > 0:
        da_estimate = revenue * 0.10
        ebitda = net_profit + da_estimate
    elif revenue and revenue > 0:
        ebitda = revenue * 0.12  # assume 12% EBITDA margin

    ebitda_margin = None
    if ebitda is not None and revenue and revenue > 0:
        ebitda_margin = round(max(-999, min(999, ebitda / revenue * 100)), 1)

    sector = raw.get("sector", "healthcare")
    ev_mult = EV_REVENUE_MULTIPLES.get(sector, 2.0)
    ev = round(revenue * ev_mult, 2) if revenue else None

    ask_multiple = None
    if ev and ebitda and ebitda > 0:
        ask_multiple = round(ev / ebitda, 1)

    # Seller intent heuristic
    seller_intent = "warm"
    if revenue and revenue > 5_000_000:
        seller_intent = "cold"
    elif revenue and revenue < 500_000:
        seller_intent = "hot"

    website = raw.get("website", "")
    if website and not website.startswith("http"):
        website = "https://" + website

    description = raw.get("description", "")
    if not description:
        description = f"{name} is a Lithuanian company based in {city or 'Lithuania'}, operating in the {raw.get('sub_sector', sector)} sector."
        if employees:
            description += f" The company employs {employees} people."
        if revenue:
            description += f" Annual revenue: €{revenue:,.0f}."

    return {
        "slug": slug,
        "name": name,
        "hq_city": city,
        "hq_state": None,
        "country": "LT",
        "sector": sector,
        "sub_sector": raw.get("sub_sector", ""),
        "website": website or None,
        "founded_year": founded,
        "employees": employees,
        "revenue_ltm": revenue,
        "ebitda_ltm": round(ebitda, 2) if ebitda else None,
        "ebitda_margin": ebitda_margin,
        "growth_rate": growth_rate,
        "ownership": "founder",
        "deal_stage": "sourced",
        "deal_type": "platform",
        "enterprise_value": ev,
        "ask_multiple": ask_multiple,
        "description": description,
        "seller_intent": seller_intent,
    }


def _transform_financials(company_id: int, raw: dict) -> list[dict]:
    """Create monthly financial rows from annual data."""
    financials = raw.get("financials", [])
    rows = []
    for fin in financials:
        year = fin.get("year")
        revenue_annual = fin.get("sales_revenue")
        net_profit_annual = fin.get("net_profit")
        if not year or not revenue_annual:
            continue

        monthly_rev = round(revenue_annual / 12, 2)
        monthly_profit = round(net_profit_annual / 12, 2) if net_profit_annual else None
        da_monthly = round(revenue_annual * 0.10 / 12, 2) if revenue_annual else 0
        monthly_ebitda = round((net_profit_annual + revenue_annual * 0.10) / 12, 2) if net_profit_annual else round(revenue_annual * 0.12 / 12, 2)

        for month_num in range(1, 13):
            rows.append({
                "company_id": company_id,
                "month": f"{year}-{month_num:02d}-01",
                "revenue": monthly_rev,
                "cogs": None,
                "gross_profit": monthly_rev,
                "opex": None,
                "ebitda": monthly_ebitda,
                "adjustments": None,
                "adj_ebitda": monthly_ebitda,
                "arr": None,
                "gross_retention": None,
                "net_retention": None,
            })
    return rows


def load(dry_run: bool = False):
    if not DATA_PATH.exists():
        log.error("Data file not found: %s", DATA_PATH)
        log.error("Run: python -m scripts.scrape_lt")
        return

    raw_companies = json.loads(DATA_PATH.read_text())
    log.info("Loaded %d raw companies from %s", len(raw_companies), DATA_PATH)

    transformed = []
    for raw in raw_companies:
        row = _transform_company(raw)
        if row:
            transformed.append((row, raw))

    log.info("Transformed %d companies (skipped %d)",
             len(transformed), len(raw_companies) - len(transformed))

    if dry_run:
        for row, _ in transformed[:10]:
            log.info("  %s | %s | %s | rev=%.0f | emp=%s",
                     row["slug"][:25], row["sector"], row["hq_city"],
                     row["revenue_ltm"] or 0, row["employees"])
        log.info("  ... (%d total)", len(transformed))
        return

    with connect() as conn, conn.cursor() as cur:
        # Truncate existing data
        for t in TRUNCATE_TABLES:
            cur.execute(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE")
            log.info("Truncated %s", t)

        companies_inserted = 0
        financials_inserted = 0

        for row, raw in transformed:
            cur.execute(
                """INSERT INTO pehero.companies
                   (slug, name, hq_city, hq_state, country, sector, sub_sector,
                    website, founded_year, employees, revenue_ltm, ebitda_ltm,
                    ebitda_margin, growth_rate, ownership, deal_stage, deal_type,
                    enterprise_value, ask_multiple, description, seller_intent)
                   VALUES (%(slug)s, %(name)s, %(hq_city)s, %(hq_state)s, %(country)s,
                           %(sector)s, %(sub_sector)s, %(website)s, %(founded_year)s,
                           %(employees)s, %(revenue_ltm)s, %(ebitda_ltm)s,
                           %(ebitda_margin)s, %(growth_rate)s, %(ownership)s,
                           %(deal_stage)s, %(deal_type)s, %(enterprise_value)s,
                           %(ask_multiple)s, %(description)s, %(seller_intent)s)
                   RETURNING id""",
                row,
            )
            company_id = cur.fetchone()[0]
            companies_inserted += 1

            fin_rows = _transform_financials(company_id, raw)
            for fr in fin_rows:
                cur.execute(
                    """INSERT INTO pehero.financials
                       (company_id, month, revenue, cogs, gross_profit, opex,
                        ebitda, adjustments, adj_ebitda, arr,
                        gross_retention, net_retention)
                       VALUES (%(company_id)s, %(month)s, %(revenue)s, %(cogs)s,
                               %(gross_profit)s, %(opex)s, %(ebitda)s, %(adjustments)s,
                               %(adj_ebitda)s, %(arr)s, %(gross_retention)s,
                               %(net_retention)s)
                       ON CONFLICT (company_id, month) DO NOTHING""",
                    fr,
                )
                financials_inserted += 1

        conn.commit()

    log.info("Inserted %d companies, %d financial rows", companies_inserted, financials_inserted)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="preview without writing to DB")
    args = ap.parse_args()
    load(dry_run=args.dry_run)
