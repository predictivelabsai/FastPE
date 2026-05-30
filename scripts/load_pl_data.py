"""Load Polish company data from data/pl_companies.json into PEHero DB.

Appends Polish companies alongside existing Baltic + RO data.
Note: Polish data from KRS API lacks financials unless enriched via
Apify or Transparent Data. Companies without revenue are still loaded
with revenue_ltm=NULL (useful for the pipeline/sourcing view).

Usage:
    python -m scripts.load_pl_data                  # load
    python -m scripts.load_pl_data --dry-run        # preview
    python -m scripts.load_pl_data --min-revenue 200000  # only with financials
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

from db import connect, fetch_one

log = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "pl_companies.json"

EV_REVENUE_MULTIPLES = {
    "healthcare": 2.5,
    "software": 3.5,
    "business_services": 1.8,
    "financial_services": 3.0,
    "industrials": 1.2,
    "consumer": 1.5,
}

PLN_TO_EUR = 1 / 4.3


def _make_slug(raw_slug: str, name: str) -> str:
    base = raw_slug or re.sub(r"[^a-z0-9]+", "_", name.lower())
    return base.strip("_")[:60]


def _transform_company(raw: dict) -> dict | None:
    name = raw.get("name", "").strip()
    if not name or len(name) < 2:
        return None

    slug = _make_slug(raw.get("slug", ""), name)
    city = raw.get("city", "")
    sector = raw.get("sector", "business_services")
    sub_sector = raw.get("sub_sector", "")

    financials = raw.get("financials", [])
    revenue = None
    net_profit = None
    growth_rate = None
    ebitda = None
    ebitda_margin = None
    ev = None
    ask_multiple = None

    if financials:
        latest = financials[-1]
        revenue_pln = latest.get("sales_revenue")
        net_profit_pln = latest.get("net_profit")

        if revenue_pln and revenue_pln > 0:
            revenue = round(revenue_pln * PLN_TO_EUR, 2)
            net_profit = round(net_profit_pln * PLN_TO_EUR, 2) if net_profit_pln else None

            if len(financials) >= 2:
                for i in range(len(financials) - 1, 0, -1):
                    r_new = financials[i].get("sales_revenue")
                    r_old = financials[i - 1].get("sales_revenue")
                    if r_new and r_old and r_old > 0:
                        growth_rate = round(max(-999, min(999, (r_new / r_old - 1) * 100)), 1)
                        break

            if net_profit is not None:
                ebitda = net_profit + revenue * 0.10
            else:
                ebitda = revenue * 0.12

            ebitda_margin = round(max(-999, min(999, ebitda / revenue * 100)), 1) if ebitda else None
            ev_mult = EV_REVENUE_MULTIPLES.get(sector, 2.0)
            ev = round(revenue * ev_mult, 2)
            ask_multiple = round(ev / ebitda, 1) if ebitda and ebitda > 0 else None

    share_cap = raw.get("share_capital_pln")
    if share_cap and not revenue:
        share_cap_eur = share_cap * PLN_TO_EUR
    else:
        share_cap_eur = None

    seller_intent = "warm"
    if revenue and revenue > 5_000_000:
        seller_intent = "cold"
    elif revenue and revenue < 500_000:
        seller_intent = "hot"

    description = f"{name} is a Polish company based in {city or 'Poland'}, operating in the {sub_sector or sector} sector."
    if revenue:
        description += f" Annual revenue: €{revenue:,.0f}."

    return {
        "slug": slug,
        "name": name,
        "hq_city": city or None,
        "hq_state": None,
        "country": "PL",
        "sector": sector,
        "sub_sector": sub_sector,
        "website": None,
        "founded_year": None,
        "employees": None,
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
        "financials": financials,
    }


def _transform_financials(company_id: int, financials: list[dict]) -> list[dict]:
    rows = []
    for fin in financials:
        year = fin.get("year")
        revenue_annual = fin.get("sales_revenue")
        net_profit_annual = fin.get("net_profit")
        if not year or not revenue_annual:
            continue

        rev_eur = revenue_annual * PLN_TO_EUR
        profit_eur = net_profit_annual * PLN_TO_EUR if net_profit_annual else None

        monthly_rev = round(rev_eur / 12, 2)
        monthly_ebitda = round((profit_eur + rev_eur * 0.10) / 12, 2) if profit_eur else round(rev_eur * 0.12 / 12, 2)

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


def load(dry_run: bool = False, min_revenue: float = 0):
    if not DATA_PATH.exists():
        log.error("Data file not found: %s", DATA_PATH)
        log.error("Run: python -m scripts.scrape_pl")
        return

    raw_companies = json.loads(DATA_PATH.read_text())
    log.info("Loaded %d raw Polish companies from %s", len(raw_companies), DATA_PATH)

    transformed = []
    skipped_no_rev = 0
    skipped_below = 0
    for raw in raw_companies:
        row = _transform_company(raw)
        if row:
            if min_revenue and (not row["revenue_ltm"] or row["revenue_ltm"] < min_revenue):
                skipped_below += 1
                continue
            transformed.append(row)
        else:
            skipped_no_rev += 1

    log.info("Transformed %d companies (skipped %d no-data, %d below €%.0f revenue)",
             len(transformed), skipped_no_rev, skipped_below, min_revenue)

    if dry_run:
        for row in transformed[:10]:
            log.info("  %s | %s | %s | rev=%s | growth=%s",
                     row["slug"][:25], row["sector"], row["hq_city"],
                     f"{row['revenue_ltm']:.0f}" if row["revenue_ltm"] else "N/A",
                     row["growth_rate"])
        log.info("  ... (%d total)", len(transformed))
        return

    with connect() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM pehero.financials WHERE company_id IN (SELECT id FROM pehero.companies WHERE country = 'PL')")
        cur.execute("DELETE FROM pehero.companies WHERE country = 'PL'")
        log.info("Cleared existing Polish companies")

        companies_inserted = 0
        financials_inserted = 0
        slug_conflicts = 0

        for row in transformed:
            existing = fetch_one("SELECT id FROM pehero.companies WHERE slug = %s", (row["slug"],))
            if existing:
                row["slug"] = row["slug"] + "_pl"
                existing2 = fetch_one("SELECT id FROM pehero.companies WHERE slug = %s", (row["slug"],))
                if existing2:
                    slug_conflicts += 1
                    continue

            financials = row.pop("financials")
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

            fin_rows = _transform_financials(company_id, financials)
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

    if slug_conflicts:
        log.warning("Skipped %d companies due to slug conflicts", slug_conflicts)
    log.info("Inserted %d Polish companies, %d financial rows", companies_inserted, financials_inserted)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="preview without writing to DB")
    ap.add_argument("--min-revenue", type=float, default=0,
                    help="minimum revenue in EUR (e.g. 200000)")
    args = ap.parse_args()
    load(dry_run=args.dry_run, min_revenue=args.min_revenue)
