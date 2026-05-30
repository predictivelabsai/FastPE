"""Fetch Latvian company data from data.gov.lv open CKAN API → data/lv_companies.json.

Latvia publishes full financial statements as open data (CC0). No scraping
needed — pure REST API, paginated JSON, no auth.

Four datasets are joined on legal_entity_registration_number:
  1. Company register   — name, address, type, dates
  2. Annual report info — employees, year
  3. Income statements  — net_turnover (revenue), net_income
  4. Balance sheets     — total_assets, equity, liabilities

Usage:
    python -m scripts.scrape_lv                     # fetch all (may take ~30 min)
    python -m scripts.scrape_lv --target 5000       # stop after N companies
    python -m scripts.scrape_lv --min-revenue 200000  # only keep companies above threshold
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "lv_companies.json"

CKAN_BASE = "https://data.gov.lv/dati/api/3/action/datastore_search"

RESOURCE_REGISTER = "25e80bf3-f107-4ab4-89ef-251b5b9374e9"
RESOURCE_REPORT_INFO = "27fcc5ec-c63b-4bfd-bb08-01f073a52d04"
RESOURCE_INCOME = "d5fd17ef-d32e-40cb-8399-82b780095af0"
RESOURCE_BALANCE = "50ef4f26-f410-4007-b296-22043ca3dc43"
RESOURCE_ACTIVITY = "49bbd751-3fa2-4d78-8c35-ae0e1c5250d6"

BATCH = 500
MAX_RETRIES = 3

NACE_TO_SECTOR = {
    "86": ("healthcare", "Healthcare"),
    "75": ("healthcare", "Veterinary"),
    "62": ("software", "Software & IT"),
    "63": ("software", "Data processing & hosting"),
    "61": ("software", "Telecommunications"),
    "64": ("financial_services", "Financial services"),
    "65": ("financial_services", "Insurance"),
    "66": ("financial_services", "Financial auxiliaries"),
    "49": ("industrials", "Land transport & logistics"),
    "50": ("industrials", "Water transport"),
    "52": ("industrials", "Warehousing & support"),
    "25": ("industrials", "Fabricated metals"),
    "28": ("industrials", "Machinery manufacturing"),
    "10": ("consumer", "Food manufacturing"),
    "11": ("consumer", "Beverages"),
    "55": ("consumer", "Accommodation"),
    "56": ("consumer", "Food & beverage service"),
    "47": ("consumer", "Retail trade"),
    "68": ("business_services", "Real estate"),
    "41": ("business_services", "Construction"),
    "42": ("business_services", "Civil engineering"),
    "43": ("business_services", "Specialised construction"),
    "69": ("business_services", "Legal & accounting"),
    "70": ("business_services", "Management consulting"),
    "71": ("business_services", "Architecture & engineering"),
    "73": ("business_services", "Advertising & market research"),
    "46": ("business_services", "Wholesale trade"),
}


def _fetch_all(resource_id: str, fields: list[str] | None = None,
               filters: dict | None = None, limit: int = 0) -> list[dict]:
    """Paginate through a CKAN datastore resource."""
    client = httpx.Client(timeout=30.0)
    offset = 0
    results = []
    params: dict = {"resource_id": resource_id, "limit": BATCH}
    if fields:
        params["fields"] = ",".join(fields)
    if filters:
        params["filters"] = json.dumps(filters)

    while True:
        params["offset"] = offset
        for attempt in range(MAX_RETRIES):
            try:
                r = client.get(CKAN_BASE, params=params)
                r.raise_for_status()
                data = r.json()
                break
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = 2 ** (attempt + 1)
                    log.warning("Retry %d for offset %d: %s (wait %ds)",
                                attempt + 1, offset, e, wait)
                    time.sleep(wait)
                else:
                    log.error("Failed after %d retries at offset %d", MAX_RETRIES, offset)
                    client.close()
                    return results

        records = data.get("result", {}).get("records", [])
        if not records:
            break
        results.extend(records)

        if limit and len(results) >= limit:
            results = results[:limit]
            break

        total = data.get("result", {}).get("total", 0)
        offset += BATCH
        if offset >= total:
            break

        if len(results) % 5000 == 0:
            log.info("  ... fetched %d / %d records", len(results), total)

    client.close()
    return results


def _guess_sector(activity_text: str) -> tuple[str, str]:
    """Map free-text Latvian activity description to sector."""
    if not activity_text:
        return "business_services", "General"
    text = activity_text.lower()
    keywords = {
        ("healthcare", "Healthcare"): ["medicīn", "veselīb", "ārstniec", "zobārstn", "aptiek",
                                        "farmac", "veterinār", "klīnik", "slimnīc"],
        ("software", "Software & IT"): ["programm", "datorteh", "informāc", "it ", "tehnoloģ",
                                         "programmatūr", "datu apstrād", "telekomunikāc"],
        ("financial_services", "Financial services"): ["finans", "apdrošināš", "bank",
                                                        "kredīt", "līzing"],
        ("industrials", "Logistics & Industry"): ["transport", "loģistik", "noliktav",
                                                    "ražošan", "metālapstrād", "mašīnbūv",
                                                    "pārvadāj"],
        ("consumer", "Consumer"): ["mazumtirdz", "viesnīc", "restorān", "ēdināšan",
                                    "pārtikas ražošan", "dzērien"],
        ("business_services", "Business services"): ["nekustam", "būvniecīb", "konsultāc",
                                                       "juridiski", "grāmatved", "reklām",
                                                       "vairumtirdz", "tirdzniecīb"],
    }
    for (sector, sub), kws in keywords.items():
        if any(kw in text for kw in kws):
            return sector, sub
    return "business_services", "General"


def _parse_date_year(date_str: str | None) -> int | None:
    if not date_str:
        return None
    m = re.search(r"(\d{4})", str(date_str))
    return int(m.group(1)) if m else None


def _parse_city(address: str | None) -> str | None:
    if not address:
        return None
    parts = [p.strip() for p in address.split(",")]
    for part in parts:
        cleaned = re.sub(r"\s+(pilsēta|novads|pagasts)$", "", part, flags=re.IGNORECASE).strip()
        if cleaned and len(cleaned) > 1:
            return cleaned
    return parts[0].strip() if parts else None


def fetch(target: int = 0, min_revenue: float = 0):
    log.info("=== Fetching Latvian company data from data.gov.lv ===")

    # 1. Company register
    log.info("Step 1/5: Fetching company register...")
    register = _fetch_all(
        RESOURCE_REGISTER,
        fields=["regcode", "name", "type", "type_text", "registered", "address"],
    )
    log.info("  Got %d companies from register", len(register))
    reg_by_code = {}
    for r in register:
        code = str(r.get("regcode", "")).strip()
        if code and r.get("name"):
            reg_by_code[code] = r

    # 2. Activity descriptions (sector)
    log.info("Step 2/5: Fetching activity descriptions...")
    activities = _fetch_all(
        RESOURCE_ACTIVITY,
        fields=["legal_entity_registration_number", "area_of_activity"],
    )
    log.info("  Got %d activity records", len(activities))
    activity_by_code = {}
    for a in activities:
        code = str(a.get("legal_entity_registration_number", "")).strip()
        if code:
            activity_by_code[code] = a.get("area_of_activity", "")

    # 3. Annual report info (employees, year → statement_id mapping)
    log.info("Step 3/5: Fetching annual report info...")
    report_info = _fetch_all(
        RESOURCE_REPORT_INFO,
        fields=["id", "legal_entity_registration_number", "year", "employees"],
    )
    log.info("  Got %d report records", len(report_info))
    reports_by_code: dict[str, list[dict]] = {}
    id_to_code: dict[int, str] = {}
    for ri in report_info:
        code = str(ri.get("legal_entity_registration_number", "")).strip()
        stmt_id = ri.get("id")
        if code and stmt_id:
            reports_by_code.setdefault(code, []).append(ri)
            id_to_code[stmt_id] = code

    # 4. Income statements
    log.info("Step 4/5: Fetching income statements...")
    incomes = _fetch_all(
        RESOURCE_INCOME,
        fields=["statement_id", "net_turnover", "net_income",
                "by_function_gross_profit", "other_operating_expenses"],
    )
    log.info("  Got %d income records", len(incomes))
    income_by_stmt: dict[int, dict] = {}
    for inc in incomes:
        sid = inc.get("statement_id")
        if sid:
            income_by_stmt[sid] = inc

    # 5. Balance sheets
    log.info("Step 5/5: Fetching balance sheets...")
    balances = _fetch_all(
        RESOURCE_BALANCE,
        fields=["statement_id", "total_assets", "equity", "total_equities",
                "current_liabilities", "non_current_liabilities", "cash"],
    )
    log.info("  Got %d balance records", len(balances))
    balance_by_stmt: dict[int, dict] = {}
    for bal in balances:
        sid = bal.get("statement_id")
        if sid:
            balance_by_stmt[sid] = bal

    # Join everything
    log.info("Joining datasets...")
    companies = []
    seen_codes = set()

    for code, reports in reports_by_code.items():
        if code in seen_codes:
            continue

        reg = reg_by_code.get(code)
        if not reg:
            continue

        name = (reg.get("name") or "").strip()
        if not name:
            continue

        financials = []
        latest_employees = None
        for ri in sorted(reports, key=lambda x: x.get("year", 0)):
            year = ri.get("year")
            stmt_id = ri.get("id")
            if not year or not stmt_id:
                continue

            emp = ri.get("employees")
            if emp and emp > 0:
                latest_employees = emp

            inc = income_by_stmt.get(stmt_id, {})
            bal = balance_by_stmt.get(stmt_id, {})

            revenue = inc.get("net_turnover")
            if revenue is None or revenue == 0:
                continue

            entry = {"year": year, "sales_revenue": revenue}
            net_income = inc.get("net_income")
            if net_income is not None:
                entry["net_profit"] = net_income
            gross_profit = inc.get("by_function_gross_profit")
            if gross_profit is not None:
                entry["gross_profit"] = gross_profit

            total_assets = bal.get("total_assets")
            if total_assets is not None:
                entry["total_assets"] = total_assets
            equity = bal.get("equity") or bal.get("total_equities")
            if equity is not None:
                entry["equity"] = equity
            cur_liab = bal.get("current_liabilities") or 0
            noncur_liab = bal.get("non_current_liabilities") or 0
            if cur_liab or noncur_liab:
                entry["liabilities"] = cur_liab + noncur_liab

            financials.append(entry)

        if not financials:
            continue

        latest_rev = financials[-1].get("sales_revenue", 0)
        if min_revenue and (not latest_rev or latest_rev < min_revenue):
            continue

        activity = activity_by_code.get(code, "")
        sector, sub_sector = _guess_sector(activity)

        address = (reg.get("address") or "").strip()
        city = _parse_city(address)
        founded = _parse_date_year(reg.get("registered"))

        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:60]

        company = {
            "name": name,
            "reg_code": code,
            "address": address,
            "founded": reg.get("registered", ""),
            "country": "LV",
            "sector": sector,
            "sub_sector": sub_sector,
            "activity_description": activity,
            "employees": latest_employees,
            "financials": financials,
            "slug": slug,
        }

        companies.append(company)
        seen_codes.add(code)

        if target and len(companies) >= target:
            break

    companies.sort(key=lambda c: c["financials"][-1].get("sales_revenue", 0), reverse=True)

    DATA_PATH.parent.mkdir(exist_ok=True)
    DATA_PATH.write_text(json.dumps(companies, indent=2, ensure_ascii=False))
    log.info("Saved %d Latvian companies to %s", len(companies), DATA_PATH)

    if companies:
        top = companies[0]
        log.info("Top company: %s — revenue €%.0f", top["name"],
                 top["financials"][-1].get("sales_revenue", 0))
        sectors = {}
        for c in companies:
            sectors[c["sector"]] = sectors.get(c["sector"], 0) + 1
        log.info("Sectors: %s", dict(sorted(sectors.items(), key=lambda x: -x[1])))

    return companies


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=0, help="stop after N companies (0=all)")
    ap.add_argument("--min-revenue", type=float, default=0,
                    help="minimum latest revenue in EUR")
    args = ap.parse_args()
    fetch(target=args.target, min_revenue=args.min_revenue)
