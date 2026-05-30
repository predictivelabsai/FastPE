"""Load Estonian company data from data/ee_companies.json into PEHero DB.

Appends Estonian companies alongside existing Lithuanian data (does NOT
truncate — run load_lt_data.py first if you need a fresh start).

Usage:
    python -m scripts.load_ee_data              # load
    python -m scripts.load_ee_data --dry-run    # preview, don't write
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

from db import connect, fetch_one

log = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "ee_companies.json"

EV_REVENUE_MULTIPLES = {
    "healthcare": 2.5,
    "software": 3.5,
    "business_services": 1.8,
    "financial_services": 3.0,
    "industrials": 1.2,
    "consumer": 1.5,
}


def _parse_founded_year(text: str) -> int | None:
    if not text:
        return None
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
    if m:
        return int(m.group(3))
    return None


def _parse_city(address: str) -> str | None:
    """Extract city from Estonian address format: 'maakond, vald/linn, ...'"""
    if not address:
        return None
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 2:
        second = parts[1].strip()
        city = re.sub(r"\s+(vald|linn)$", "", second).strip()
        if city:
            return city
    return None


def _merge_financials(financials: list[dict]) -> list[dict]:
    """Merge duplicate year entries, keeping the richest record per year."""
    by_year: dict[int, dict] = {}
    for f in financials:
        year = f.get("year")
        if not year:
            continue
        if year not in by_year:
            by_year[year] = dict(f)
        else:
            existing = by_year[year]
            for k, v in f.items():
                if v is not None and (existing.get(k) is None or k != "year"):
                    if k == "sales_revenue":
                        if v and (existing.get(k) is None or v > existing[k]):
                            existing[k] = v
                    else:
                        if existing.get(k) is None:
                            existing[k] = v
    return sorted(by_year.values(), key=lambda f: f.get("year", 0))


def _make_slug(raw_slug: str, name: str) -> str:
    base = raw_slug or re.sub(r"[^a-z0-9]+", "_", name.lower())
    return base.strip("_")[:60]


def _transform_company(raw: dict) -> dict | None:
    name = raw.get("name", "").strip()
    if not name or len(name) < 2:
        return None

    financials = _merge_financials(raw.get("financials", []))

    revenue = None
    net_profit = None
    if financials:
        latest = financials[-1]
        revenue = latest.get("sales_revenue")
        net_profit = latest.get("net_profit")

    if not revenue or revenue <= 0:
        return None

    slug = _make_slug(raw.get("slug", ""), name)
    city = _parse_city(raw.get("address", ""))
    founded = _parse_founded_year(raw.get("founded", ""))

    growth_rate = None
    if len(financials) >= 2:
        for i in range(len(financials) - 1, 0, -1):
            r_new = financials[i].get("sales_revenue")
            r_old = financials[i - 1].get("sales_revenue")
            if r_new and r_old and r_old > 0:
                growth_rate = round(max(-999, min(999, (r_new / r_old - 1) * 100)), 1)
                break

    ebitda = None
    if net_profit is not None and revenue > 0:
        da_estimate = revenue * 0.10
        ebitda = net_profit + da_estimate
    elif revenue > 0:
        ebitda = revenue * 0.12

    ebitda_margin = None
    if ebitda is not None and revenue > 0:
        ebitda_margin = round(max(-999, min(999, ebitda / revenue * 100)), 1)

    sector = raw.get("sector", "business_services")
    ev_mult = EV_REVENUE_MULTIPLES.get(sector, 2.0)
    ev = round(revenue * ev_mult, 2)

    ask_multiple = None
    if ev and ebitda and ebitda > 0:
        ask_multiple = round(ev / ebitda, 1)

    seller_intent = "warm"
    if revenue > 5_000_000:
        seller_intent = "cold"
    elif revenue < 500_000:
        seller_intent = "hot"

    website = (raw.get("website") or "").strip()
    if website and not website.startswith("http"):
        website = "https://" + website

    description = raw.get("description", "")
    boilerplate = ("Add ", "data to your information", "one click", "CSV file", "Storybook")
    if not description or any(b in description for b in boilerplate):
        description = f"{name} is an Estonian company based in {city or 'Estonia'}, operating in the {raw.get('sub_sector', sector)} sector."
        if revenue:
            description += f" Annual revenue: €{revenue:,.0f}."

    return {
        "slug": slug,
        "name": name,
        "hq_city": city,
        "hq_state": None,
        "country": "EE",
        "sector": sector,
        "sub_sector": raw.get("sub_sector", ""),
        "website": website or None,
        "founded_year": founded,
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

        monthly_rev = round(revenue_annual / 12, 2)
        monthly_profit = round(net_profit_annual / 12, 2) if net_profit_annual else None
        da_monthly = round(revenue_annual * 0.10 / 12, 2)
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


def load(dry_run: bool = False, min_revenue: float = 0):
    if not DATA_PATH.exists():
        log.error("Data file not found: %s", DATA_PATH)
        log.error("Run: python -m scripts.scrape_ee")
        return

    raw_companies = json.loads(DATA_PATH.read_text())
    log.info("Loaded %d raw Estonian companies from %s", len(raw_companies), DATA_PATH)

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
            log.info("  %s | %s | %s | rev=%.0f | growth=%s",
                     row["slug"][:25], row["sector"], row["hq_city"],
                     row["revenue_ltm"] or 0, row["growth_rate"])
        log.info("  ... (%d total)", len(transformed))
        return

    with connect() as conn, conn.cursor() as cur:
        # Delete existing Estonian companies (keep Lithuanian)
        cur.execute("DELETE FROM pehero.financials WHERE company_id IN (SELECT id FROM pehero.companies WHERE country = 'EE')")
        cur.execute("DELETE FROM pehero.companies WHERE country = 'EE'")
        log.info("Cleared existing Estonian companies")

        companies_inserted = 0
        financials_inserted = 0
        slug_conflicts = 0

        for row in transformed:
            existing = fetch_one("SELECT id FROM pehero.companies WHERE slug = %s", (row["slug"],))
            if existing:
                row["slug"] = row["slug"] + "_ee"
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
    log.info("Inserted %d Estonian companies, %d financial rows", companies_inserted, financials_inserted)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="preview without writing to DB")
    ap.add_argument("--min-revenue", type=float, default=0,
                    help="minimum revenue in EUR (e.g. 200000)")
    args = ap.parse_args()
    load(dry_run=args.dry_run, min_revenue=args.min_revenue)
