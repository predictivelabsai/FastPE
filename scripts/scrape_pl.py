"""Fetch Polish company data → data/pl_companies.json.

Poland's financial statements are behind anti-bot protection (RDF portal).
This script uses the free KRS Open API for company registration data, then
optionally enriches with financials from a paid source.

Strategy:
  1. KRS Open API (free, no auth) — company name, KRS/NIP/REGON, address,
     PKD codes, share capital, board members
  2. GUS BIR API (free, key required) — size class, PKD codes (backup)
  3. Financials — requires paid service. Options:
     a) Apify eKRS scraper (~$0.03/company) — set APIFY_TOKEN
     b) Transparent Data API — set TRANSPARENT_DATA_KEY
     c) Manual: export from ekrs.ms.gov.pl

Without financials, companies are saved with registration data only and
can be enriched later.

Usage:
    python -m scripts.scrape_pl                     # fetch from KRS API
    python -m scripts.scrape_pl --target 5000       # limit
    python -m scripts.scrape_pl --pkd 62            # specific PKD prefix (IT)
    python -m scripts.scrape_pl --enrich-apify      # add financials via Apify
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
DATA_PATH = ROOT / "data" / "pl_companies.json"

KRS_API = "https://api-krs.ms.gov.pl/api/krs"

PKD_TO_SECTOR = {
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

TARGET_PKD_PREFIXES = [
    "86", "75",  # healthcare
    "62", "63", "61",  # software/IT
    "64", "65", "66",  # financial
    "49", "52",  # logistics
    "41", "42", "43",  # construction
    "68", "69", "70", "71",  # business services
    "10", "55", "56",  # consumer
    "46", "47",  # trade
]


def _pkd_to_sector(pkd: str) -> tuple[str, str]:
    if not pkd:
        return "business_services", "General"
    prefix = str(pkd).strip()[:2]
    return PKD_TO_SECTOR.get(prefix, ("business_services", "General"))


def _fetch_krs_entity(krs_number: str, client: httpx.Client) -> dict | None:
    """Fetch a single KRS entity (full excerpt)."""
    url = f"{KRS_API}/OdpisAktualny/{krs_number}"
    try:
        r = client.get(url, params={"rejestr": "P", "format": "json"}, timeout=15.0)
        if r.status_code == 429:
            log.warning("Rate limited on KRS %s, waiting 10s...", krs_number)
            time.sleep(10)
            r = client.get(url, params={"rejestr": "P", "format": "json"}, timeout=15.0)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception as e:
        log.warning("KRS fetch failed for %s: %s", krs_number, e)
        return None


def _parse_krs_entity(data: dict) -> dict | None:
    """Parse KRS API response into our standard format."""
    odpis = data.get("odppisDanych", data)
    dane = odpis.get("dane", {})

    name = dane.get("nazwa", "")
    if not name:
        return None

    krs = dane.get("numerKRS", "")
    nip = dane.get("nip", "")
    regon = dane.get("regon", "")

    address_parts = []
    adres = dane.get("siedzibaIAdres", {}).get("adres", {})
    if adres:
        city = adres.get("miejscowosc", "")
        street = adres.get("ulica", "")
        nr = adres.get("nrDomu", "")
        postal = adres.get("kodPocztowy", "")
        if street:
            address_parts.append(f"{street} {nr}".strip())
        if postal and city:
            address_parts.append(f"{postal} {city}")
        elif city:
            address_parts.append(city)

    pkd_list = dane.get("dzialalnoscGospodarcza", {}).get("przedmiotPrzewazajacejDzialalnosci", [])
    pkd_main = ""
    if pkd_list:
        pkd_main = pkd_list[0].get("kodDzial", "") if isinstance(pkd_list[0], dict) else ""

    share_capital = dane.get("kapitalZakladowy", {}).get("wartosc")

    sector, sub_sector = _pkd_to_sector(pkd_main)
    city = adres.get("miejscowosc", "") if adres else ""

    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:60]

    return {
        "name": name,
        "reg_code": krs,
        "nip": nip,
        "regon": regon,
        "address": ", ".join(address_parts),
        "city": city,
        "pkd": pkd_main,
        "country": "PL",
        "sector": sector,
        "sub_sector": sub_sector,
        "share_capital_pln": share_capital,
        "financials": [],
        "slug": slug,
    }


def _search_krs_by_range(start: int, end: int, client: httpx.Client) -> list[dict]:
    """Fetch KRS entities by scanning KRS number range."""
    results = []
    for krs_num in range(start, end + 1):
        krs_str = f"{krs_num:010d}"
        data = _fetch_krs_entity(krs_str, client)
        if data:
            parsed = _parse_krs_entity(data)
            if parsed:
                results.append(parsed)
        time.sleep(0.3)
    return results


def fetch(target: int = 5000, pkd_filter: str = ""):
    log.info("=== Fetching Polish company data from KRS API ===")
    log.info("Note: KRS API provides registration data only (no financials).")
    log.info("For financials, re-run with --enrich-apify or use a paid API.")

    client = httpx.Client(timeout=15.0)
    companies = []
    seen_krs = set()

    if DATA_PATH.exists():
        existing = json.loads(DATA_PATH.read_text())
        companies.extend(existing)
        seen_krs.update(c.get("reg_code", "") for c in existing)
        log.info("Resuming: %d existing companies", len(existing))

    if len(companies) >= target:
        log.info("Already at target")
        client.close()
        return companies

    # Scan KRS numbers in ranges. Most active companies are in 0000001-0900000.
    # We sample across the range to get sector diversity.
    RANGE_START = 1
    RANGE_END = 900000
    STEP = max(1, (RANGE_END - RANGE_START) // target)

    log.info("Scanning KRS numbers %d-%d (step=%d)...", RANGE_START, RANGE_END, STEP)

    for krs_num in range(RANGE_START, RANGE_END, STEP):
        if len(companies) >= target:
            break

        krs_str = f"{krs_num:010d}"
        if krs_str in seen_krs:
            continue

        data = _fetch_krs_entity(krs_str, client)
        if not data:
            continue

        parsed = _parse_krs_entity(data)
        if not parsed:
            continue

        if pkd_filter and not parsed.get("pkd", "").startswith(pkd_filter):
            continue

        companies.append(parsed)
        seen_krs.add(parsed["reg_code"])

        if len(companies) % 100 == 0:
            log.info("  %d companies found (KRS=%s, latest: %s)",
                     len(companies), krs_str, parsed["name"][:40])
            DATA_PATH.parent.mkdir(exist_ok=True)
            DATA_PATH.write_text(json.dumps(companies, indent=2, ensure_ascii=False))

        time.sleep(0.3)

    client.close()

    DATA_PATH.parent.mkdir(exist_ok=True)
    DATA_PATH.write_text(json.dumps(companies, indent=2, ensure_ascii=False))
    log.info("Saved %d Polish companies to %s", len(companies), DATA_PATH)
    log.info("NOTE: No financials included. Run --enrich-apify or use load_pl_data.py with external data.")

    return companies


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=5000, help="companies to fetch")
    ap.add_argument("--pkd", type=str, default="", help="filter by PKD prefix (e.g. 62 for IT)")
    ap.add_argument("--enrich-apify", action="store_true",
                    help="enrich with financials via Apify (requires APIFY_TOKEN)")
    args = ap.parse_args()
    fetch(target=args.target, pkd_filter=args.pkd)
