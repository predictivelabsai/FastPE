"""Scrape Estonian company ownership data from ariregister.rik.ee.

Uses the public autocomplete API to find reg codes, then scrapes the
company page for shareholders (Osanikud) and beneficial owners.

Usage:
    python -m scripts.scrape_ee_owners                 # scrape + update DB
    python -m scripts.scrape_ee_owners --dry-run       # preview, don't write
    python -m scripts.scrape_ee_owners --limit 20      # first N companies
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from pathlib import Path

import httpx

from db import connect, fetch_all

log = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "ee_owners.json"

API_BASE = "https://ariregister.rik.ee/est/api/autocomplete"


def _search_reg_code(name: str) -> tuple[int | None, str | None]:
    short = re.sub(r"\s+(OÜ|AS|MTÜ|SA|TÜ|UÜ|FIE)$", "", name, flags=re.IGNORECASE).strip()
    if len(short) < 3:
        short = name
    try:
        resp = httpx.get(API_BASE, params={"q": short, "results": 5}, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except Exception as e:
        log.warning("API search failed for %s: %s", short, e)
        return None, None

    if not data:
        return None, None

    name_lower = name.lower().strip()
    for d in data:
        if d["name"].lower().strip() == name_lower:
            return d["reg_code"], d.get("url")

    return data[0]["reg_code"], data[0].get("url")


def _classify_ownership(shareholders: list[dict]) -> str:
    if not shareholders:
        return "unknown"

    person_pct = 0.0
    ee_co_pct = 0.0
    foreign_pct = 0.0

    for sh in shareholders:
        pct = sh.get("pct_num", 0)
        code = sh.get("code", "")

        is_person = bool(re.search(r"\d{10,11}$", code.strip()))
        is_foreign = any(
            x in code
            for x in (
                "Soome", "Rootsi", "Ameerika", "Holland", "Saksa",
                "Taani", "Norra", "Läti", "Suurbritannia", "Leedu",
                "USSR", "Luksemburg", "Iirimaa", "Küpros", "Šveits",
            )
        )
        is_ee_co = not is_person and not is_foreign and re.search(r"\d{7,8}$", code.strip())

        if is_person:
            person_pct += pct
        elif is_foreign:
            foreign_pct += pct
        elif is_ee_co:
            ee_co_pct += pct

    if person_pct >= 50:
        return "founder"
    if foreign_pct >= 50:
        return "corporate_carve_out"
    if ee_co_pct >= 50:
        return "pe_backed"
    if person_pct > 0 and person_pct > ee_co_pct and person_pct > foreign_pct:
        return "founder"
    return "pe_backed"


def _extract_shareholders(page) -> dict:
    return page.evaluate(r"""() => {
        const result = {shareholders: [], beneficial_owners: [], reg_code: ''};
        const m = document.title.match(/\((\d+)\)/);
        if (m) result.reg_code = m[1];
        for (const table of document.querySelectorAll('table')) {
            const h = [...table.querySelectorAll('th')].map(t => t.textContent.trim()).join('|');
            if (h.includes('Osalus') && h.includes('Osamaks'))
                for (const row of table.querySelectorAll('tbody tr')) {
                    const c = [...row.querySelectorAll('td')].map(c => c.textContent.trim());
                    if (c.length >= 3) result.shareholders.push({pct: c[0], name: c[2], code: c[3] || ''});
                }
            if (h.includes('Kontrolli'))
                for (const row of table.querySelectorAll('tbody tr')) {
                    const c = [...row.querySelectorAll('td')].map(c => c.textContent.trim());
                    if (c.length >= 3) result.beneficial_owners.push({name: c[0], control: c[2]});
                }
        }
        return result;
    }""")


def scrape(limit: int | None = None, dry_run: bool = False):
    from playwright.sync_api import sync_playwright

    companies = fetch_all("""
        SELECT id, name, slug FROM pehero.companies
        WHERE country = 'EE'
        ORDER BY revenue_ltm DESC NULLS LAST
    """)
    if limit:
        companies = companies[:limit]

    log.info("Scraping ownership for %d Estonian companies", len(companies))

    results = []
    no_match = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(locale="et-EE")
        page = ctx.new_page()

        page.goto("https://ariregister.rik.ee/est", timeout=20000)
        page.wait_for_load_state("domcontentloaded")
        try:
            page.click("text=Nõustun", timeout=3000)
        except Exception:
            pass

        for i, co in enumerate(companies):
            name = co["name"]

            reg_code, url = _search_reg_code(name)
            if not reg_code:
                no_match += 1
                results.append({"id": co["id"], "name": name, "error": "no_match"})
                if (i + 1) % 50 == 0:
                    log.info("[%d/%d] progress (no_match so far: %d)", i + 1, len(companies), no_match)
                continue

            try:
                if url:
                    page.goto(url, timeout=15000)
                else:
                    page.goto(
                        f"https://ariregister.rik.ee/est/company/{reg_code}/",
                        timeout=15000,
                    )
                page.wait_for_load_state("domcontentloaded")
                time.sleep(0.8)

                data = _extract_shareholders(page)

                for sh in data["shareholders"]:
                    pct_str = sh["pct"].replace("%", "").replace(",", ".").strip()
                    try:
                        sh["pct_num"] = float(pct_str)
                    except ValueError:
                        sh["pct_num"] = 0

                ownership = _classify_ownership(data["shareholders"])
                data["ownership"] = ownership
                data["id"] = co["id"]
                data["db_name"] = name
                data["reg_code"] = str(reg_code)
                results.append(data)

                if (i + 1) % 10 == 0:
                    log.info(
                        "[%d/%d] %s → %s (%d sh)",
                        i + 1, len(companies), name[:35], ownership,
                        len(data["shareholders"]),
                    )

            except Exception as e:
                log.warning("[%d/%d] %s — %s", i + 1, len(companies), name[:30], str(e)[:60])
                results.append({"id": co["id"], "name": name, "error": str(e)[:100]})

            time.sleep(0.3)

        browser.close()

    DATA_PATH.parent.mkdir(exist_ok=True)
    DATA_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    matched = [r for r in results if "ownership" in r]
    by_type = {}
    for r in matched:
        o = r["ownership"]
        by_type[o] = by_type.get(o, 0) + 1
    log.info(
        "Done: %d matched, %d no_match. Breakdown: %s",
        len(matched), no_match,
        ", ".join(f"{k}={v}" for k, v in sorted(by_type.items())),
    )

    if dry_run:
        for r in matched[:30]:
            shs = r.get("shareholders", [])
            sh_summary = ", ".join(f"{s['pct']} {s['name'][:25]}" for s in shs[:3])
            log.info("  %-40s  → %-20s  %s", r["db_name"][:40], r["ownership"], sh_summary)
        return

    updated = 0
    with connect() as conn, conn.cursor() as cur:
        for r in matched:
            cur.execute(
                "UPDATE pehero.companies SET ownership = %s WHERE id = %s",
                (r["ownership"], r["id"]),
            )
            updated += 1
        conn.commit()
    log.info("Updated ownership for %d companies", updated)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    scrape(limit=args.limit, dry_run=args.dry_run)
