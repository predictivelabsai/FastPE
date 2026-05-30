"""Fetch Romanian company data from ANAF + data.gov.ro → data/ro_companies.json.

Two-step process:
  1. Download base company registry from data.gov.ro ONRC open data (CUI, name, CAEN, county)
  2. Enrich with financial data from ANAF bilant API (free, no auth, 1 req/sec)

Usage:
    python -m scripts.scrape_ro                         # fetch all
    python -m scripts.scrape_ro --target 10000          # stop after N companies
    python -m scripts.scrape_ro --min-revenue 200000    # only keep above threshold
    python -m scripts.scrape_ro --skip-registry         # skip registry download, reuse cached
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
DATA_PATH = ROOT / "data" / "ro_companies.json"
REGISTRY_CACHE = ROOT / "data" / "ro_registry_cache.json"

ANAF_BILANT = "https://webservicesp.anaf.ro/bilant"
ANAF_TVA = "https://webservicesp.anaf.ro/PlatitorTvaRest/api/v8/ws/tva"
ONRC_CKAN = "https://data.gov.ro/api/3/action"

CAEN_TO_SECTOR = {
    "86": ("healthcare", "Healthcare"),
    "87": ("healthcare", "Residential care"),
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

YEARS_TO_FETCH = [2024, 2023, 2022, 2021, 2020]


def _caen_to_sector(caen: str) -> tuple[str, str]:
    if not caen:
        return "business_services", "General"
    prefix = str(caen).strip()[:2]
    return CAEN_TO_SECTOR.get(prefix, ("business_services", "General"))


FIRME_CSV_URL = (
    "https://data.gov.ro/dataset/6ea515d8-6d38-4a57-acfd-62aa13b4a1a5/"
    "resource/07f56a43-461d-40da-898c-b29d7ebfee32/download/od_firme.csv"
)
CAEN_CSV_URL = (
    "https://data.gov.ro/dataset/6ea515d8-6d38-4a57-acfd-62aa13b4a1a5/"
    "resource/0da22c09-6160-4fda-88e2-3f37b9de72d0/download/od_caen_autorizat.csv"
)


def _fetch_onrc_registry() -> list[dict]:
    """Download company list from ONRC CSV files on data.gov.ro.

    CSV format: ^-delimited. OD_FIRME has name/CUI/address.
    OD_CAEN_AUTORIZAT has CUI→CAEN mapping.
    Only keeps SRL/SA/SCS/SNC (legal entities relevant for PE).
    """
    if REGISTRY_CACHE.exists():
        cached = json.loads(REGISTRY_CACHE.read_text())
        log.info("Using cached registry: %d companies", len(cached))
        return cached

    import csv
    import io

    client = httpx.Client(timeout=120.0, follow_redirects=True)

    # Step 1: Download CAEN codes
    log.info("Downloading CAEN codes...")
    try:
        r = client.get(CAEN_CSV_URL)
        r.raise_for_status()
        text = r.text.lstrip("﻿")
        reader = csv.reader(io.StringIO(text), delimiter="^")
        header = next(reader)
        log.info("  CAEN header: %s", header)
        cui_idx = next(i for i, h in enumerate(header) if "CUI" in h.upper())
        caen_idx = next(i for i, h in enumerate(header) if "CAEN" in h.upper())
        caen_by_cui: dict[str, str] = {}
        for row in reader:
            if len(row) > max(cui_idx, caen_idx):
                cui = row[cui_idx].strip()
                caen = row[caen_idx].strip()
                if cui and caen and cui != "0":
                    caen_by_cui.setdefault(cui, caen)
        log.info("  Loaded %d CAEN mappings", len(caen_by_cui))
    except Exception as e:
        log.warning("Failed to load CAEN file: %s", e)
        caen_by_cui = {}

    # Step 2: Download main company file
    log.info("Downloading OD_FIRME.CSV (~800K companies)...")
    try:
        r = client.get(FIRME_CSV_URL)
        r.raise_for_status()
    except Exception as e:
        log.error("Failed to download OD_FIRME.CSV: %s", e)
        client.close()
        return []

    text = r.text.lstrip("﻿")
    reader = csv.reader(io.StringIO(text), delimiter="^")
    header = next(reader)
    log.info("  Header: %s", header[:10])

    col = {h.upper(): i for i, h in enumerate(header)}
    name_i = col.get("DENUMIRE", 0)
    cui_i = col.get("CUI", 1)
    forma_i = col.get("FORMA_JURIDICA")
    judet_i = col.get("ADR_JUDET")
    loc_i = col.get("ADR_LOCALITATE")

    PE_FORMS = {"SRL", "SA", "SCS", "SNC", "SCA", "RA"}

    companies = []
    seen = set()
    for row in reader:
        if len(row) <= max(name_i, cui_i):
            continue
        cui = row[cui_i].strip()
        if not cui or cui == "0" or not cui.isdigit() or cui in seen:
            continue
        name = row[name_i].strip()
        if not name:
            continue
        if forma_i is not None and len(row) > forma_i:
            forma = row[forma_i].strip().upper()
            if forma and forma not in PE_FORMS:
                continue

        company: dict = {"cui": cui, "name": name}
        if judet_i is not None and len(row) > judet_i:
            company["county"] = row[judet_i].strip()
        if loc_i is not None and len(row) > loc_i:
            company["locality"] = row[loc_i].strip()
        company["caen"] = caen_by_cui.get(cui, "")

        companies.append(company)
        seen.add(cui)

        if len(companies) % 50000 == 0:
            log.info("  ... %d companies parsed", len(companies))

    client.close()

    REGISTRY_CACHE.parent.mkdir(exist_ok=True)
    REGISTRY_CACHE.write_text(json.dumps(companies, indent=2, ensure_ascii=False))
    log.info("Cached %d companies to %s", len(companies), REGISTRY_CACHE)

    return companies


def _fetch_anaf_bilant(cui: str, year: int, client: httpx.Client) -> dict | None:
    """Fetch financial data from ANAF bilant API.

    Response format: {"an", "cui", "i": [{"indicator": "I13", "val_indicator": 123, ...}, ...]}
    Key indicators: I13=net revenue, I14=total revenue, I15=total expenses,
    I16=gross profit, I18=net profit, I20=avg employees,
    I1=non-current assets, I2=current assets, I7=liabilities, I10=equity.
    """
    try:
        r = client.get(ANAF_BILANT, params={"an": year, "cui": cui}, timeout=15.0)
        if r.status_code != 200:
            return None
        data = r.json()
        if not isinstance(data, dict):
            return None
        indicators = data.get("i", [])
        if not indicators:
            return None
        result = {"year": year, "caen": data.get("caen")}
        for item in indicators:
            ind = item.get("indicator", "")
            val = item.get("val_indicator")
            if val is None:
                continue
            result[ind] = val
        return result
    except Exception:
        return None


def _fetch_anaf_company_info(cuis: list[str], client: httpx.Client) -> dict[str, dict]:
    """Batch fetch company info from ANAF TVA endpoint (up to 100 per request)."""
    results = {}
    for i in range(0, len(cuis), 100):
        batch = cuis[i:i + 100]
        payload = [{"cui": int(c), "data": "2026-05-30"} for c in batch]
        try:
            r = client.post(ANAF_TVA, json=payload, timeout=15.0)
            if r.status_code == 200:
                data = r.json()
                for item in data.get("found", []):
                    cui = str(item.get("date_generale", {}).get("cui", ""))
                    if cui:
                        results[cui] = item.get("date_generale", {})
        except Exception as e:
            log.warning("ANAF TVA batch failed: %s", e)
        time.sleep(1)
    return results


def _parse_anaf_financials(data: dict) -> dict | None:
    """Parse ANAF bilant indicators into our standard financial format.

    Indicators: I13=net revenue, I16=gross profit, I18=net profit,
    I20=employees, I1+I2=total assets, I7=liabilities, I10=equity.
    """
    year = data.get("year")
    revenue = data.get("I13")
    if not revenue or not year:
        return None

    entry = {"year": year, "sales_revenue": float(revenue)}

    net_profit = data.get("I18")
    gross_profit = data.get("I16")
    employees = data.get("I20")
    total_assets_nc = data.get("I1", 0) or 0
    total_assets_c = data.get("I2", 0) or 0
    liabilities = data.get("I7")
    equity = data.get("I10")

    if net_profit is not None:
        entry["net_profit"] = float(net_profit)
    if gross_profit is not None:
        entry["gross_profit"] = float(gross_profit)
    if total_assets_nc or total_assets_c:
        entry["total_assets"] = float(total_assets_nc + total_assets_c)
    if equity is not None:
        entry["equity"] = float(equity)
    if liabilities is not None:
        entry["liabilities"] = float(liabilities)
    if employees is not None:
        entry["employees"] = int(employees)

    return entry


def fetch(target: int = 0, min_revenue: float = 0, skip_registry: bool = False):
    log.info("=== Fetching Romanian company data ===")

    # Step 1: Get company registry
    if skip_registry and REGISTRY_CACHE.exists():
        registry = json.loads(REGISTRY_CACHE.read_text())
        log.info("Using cached registry: %d companies", len(registry))
    else:
        registry = _fetch_onrc_registry()

    if not registry:
        log.error("No companies found in registry. Check data.gov.ro connectivity.")
        return []

    log.info("Registry: %d companies. Fetching financials from ANAF...")

    # Step 2: Fetch financials from ANAF for each company
    client = httpx.Client(timeout=15.0)
    companies = []
    checked = 0
    skipped_no_fin = 0

    for comp in registry:
        if target and len(companies) >= target:
            break

        cui = comp["cui"]
        checked += 1

        financials = []
        latest_employees = None
        for year in YEARS_TO_FETCH:
            data = _fetch_anaf_bilant(cui, year, client)
            if data:
                parsed = _parse_anaf_financials(data)
                if parsed:
                    financials.append(parsed)
                    emp = parsed.pop("employees", None)
                    if emp:
                        latest_employees = emp
                    caen_from_anaf = data.get("caen")
                    if caen_from_anaf and not comp.get("caen"):
                        comp["caen"] = str(caen_from_anaf)
            time.sleep(1)

        if not financials:
            skipped_no_fin += 1
            if checked % 500 == 0:
                log.info("  Checked %d, found %d with financials (skipped %d)",
                         checked, len(companies), skipped_no_fin)
            continue

        financials.sort(key=lambda f: f.get("year", 0))
        latest_rev = financials[-1].get("sales_revenue", 0)

        if min_revenue and latest_rev < min_revenue:
            continue

        caen = comp.get("caen", "")
        sector, sub_sector = _caen_to_sector(caen)

        slug = re.sub(r"[^a-z0-9]+", "_", comp["name"].lower()).strip("_")[:60]

        company = {
            "name": comp["name"],
            "reg_code": cui,
            "caen": caen,
            "county": comp.get("county", ""),
            "country": "RO",
            "sector": sector,
            "sub_sector": sub_sector,
            "employees": latest_employees,
            "financials": financials,
            "slug": slug,
        }
        companies.append(company)

        if len(companies) % 100 == 0:
            log.info("  Found %d companies with revenue >= €%.0f (checked %d)",
                     len(companies), min_revenue, checked)
            DATA_PATH.parent.mkdir(exist_ok=True)
            DATA_PATH.write_text(json.dumps(companies, indent=2, ensure_ascii=False))

    client.close()

    companies.sort(key=lambda c: c["financials"][-1].get("sales_revenue", 0), reverse=True)
    DATA_PATH.parent.mkdir(exist_ok=True)
    DATA_PATH.write_text(json.dumps(companies, indent=2, ensure_ascii=False))
    log.info("Saved %d Romanian companies to %s (checked %d total)",
             len(companies), DATA_PATH, checked)

    if companies:
        top = companies[0]
        log.info("Top company: %s — revenue €%.0f", top["name"],
                 top["financials"][-1].get("sales_revenue", 0))

    return companies


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=0, help="stop after N companies (0=all)")
    ap.add_argument("--min-revenue", type=float, default=0,
                    help="minimum latest revenue in EUR")
    ap.add_argument("--skip-registry", action="store_true",
                    help="skip registry download, use cached")
    args = ap.parse_args()
    fetch(target=args.target, min_revenue=args.min_revenue, skip_registry=args.skip_registry)
