"""Batch scraper: Estonian companies from ssb.ee → data/ee_companies.json.

Uses EMTAK sector codes to find companies, then scrapes each company's
overview + financial data pages. Resumes from existing data automatically.

Usage:
    python -m scripts.scrape_ee                        # scrape all categories
    python -m scripts.scrape_ee --target 500           # stop at 500 companies
    python -m scripts.scrape_ee --limit-per-cat 50     # max per EMTAK category
    python -m scripts.scrape_ee --pages 3              # max listing pages
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from pathlib import Path

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "ee_companies.json"

BASE = "https://ssb.ee/en"

# EMTAK codes → PEHero sector mapping
EMTAK_CATEGORIES = {
    # Healthcare
    "86210": {"sector": "healthcare", "sub_sector": "General medical practice", "priority": 1},
    "86220": {"sector": "healthcare", "sub_sector": "Specialist medical practice", "priority": 1},
    "86230": {"sector": "healthcare", "sub_sector": "Dental practice", "priority": 1},
    "86901": {"sector": "healthcare", "sub_sector": "Ambulance & emergency services", "priority": 2},
    "86909": {"sector": "healthcare", "sub_sector": "Other healthcare", "priority": 2},
    "75001": {"sector": "healthcare", "sub_sector": "Veterinary clinics", "priority": 2},
    "46462": {"sector": "healthcare", "sub_sector": "Medical devices wholesale", "priority": 3},
    # Software / Technology
    "62011": {"sector": "software", "sub_sector": "Software development", "priority": 1},
    "62021": {"sector": "software", "sub_sector": "IT consulting", "priority": 1},
    "62031": {"sector": "software", "sub_sector": "IT infrastructure", "priority": 2},
    "63111": {"sector": "software", "sub_sector": "Data processing & hosting", "priority": 2},
    "61101": {"sector": "software", "sub_sector": "Telecom services", "priority": 3},
    "26200": {"sector": "software", "sub_sector": "Computer manufacturing", "priority": 3},
    # Financial services / Insurance
    "65111": {"sector": "financial_services", "sub_sector": "Life insurance", "priority": 1},
    "65121": {"sector": "financial_services", "sub_sector": "Non-life insurance", "priority": 1},
    "66220": {"sector": "financial_services", "sub_sector": "Insurance brokerage", "priority": 2},
    "64191": {"sector": "financial_services", "sub_sector": "Banking", "priority": 2},
    "64921": {"sector": "financial_services", "sub_sector": "Credit & lending", "priority": 3},
    # Industrials / Logistics
    "49411": {"sector": "industrials", "sub_sector": "Road freight transport", "priority": 1},
    "52291": {"sector": "industrials", "sub_sector": "Freight forwarding", "priority": 1},
    "52101": {"sector": "industrials", "sub_sector": "Warehousing", "priority": 2},
    "52241": {"sector": "industrials", "sub_sector": "Cargo handling", "priority": 2},
    "25620": {"sector": "industrials", "sub_sector": "Metal machining", "priority": 3},
    # Business services / Real estate
    "68201": {"sector": "business_services", "sub_sector": "Real estate rental", "priority": 1},
    "68311": {"sector": "business_services", "sub_sector": "Real estate brokerage", "priority": 2},
    "41201": {"sector": "business_services", "sub_sector": "Construction", "priority": 2},
    "70221": {"sector": "business_services", "sub_sector": "Management consulting", "priority": 2},
    "69101": {"sector": "business_services", "sub_sector": "Legal services", "priority": 3},
    # Consumer
    "10110": {"sector": "consumer", "sub_sector": "Meat processing", "priority": 3},
    "56101": {"sector": "consumer", "sub_sector": "Restaurants", "priority": 3},
    "55101": {"sector": "consumer", "sub_sector": "Hotels", "priority": 3},
}

# Known mid-size Estonian companies to always include
MUST_INCLUDE_CODES = [
    "12645067",  # Confido (healthcare)
    "10810826",  # AS Medicum
    "10412433",  # Fertilitas
    "10223439",  # Bolt Technology (software)
    "14060705",  # Veriff (software)
    "10078457",  # Semetron (medical devices)
    "10239452",  # Fujitsu Estonia (IT)
    "11298095",  # CMA CGM Estonia (logistics)
]


def _scrape_company_page(page, reg_code: str, name_slug: str) -> dict | None:
    """Scrape company overview from ssb.ee."""
    url = f"{BASE}/{reg_code}-{name_slug}"
    try:
        page.goto(url, timeout=20000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(1.5)
    except Exception as e:
        log.warning("Failed to load %s: %s", reg_code, e)
        return None

    try:
        data = page.evaluate("""() => {
            const result = {};
            const h1 = document.querySelector('h1');
            result.name = h1 ? h1.textContent.trim() : '';

            // Get all text content and parse key-value pairs
            const allText = document.body.innerText;

            // Registry code
            const regMatch = allText.match(/Registry code[:\\s]+(\\d+)/i);
            if (regMatch) result.reg_code = regMatch[1];

            // VAT
            const vatMatch = allText.match(/VAT[:\\s]+(EE\\d+)/i);
            if (vatMatch) result.vat = vatMatch[1];

            // Address
            const addrMatch = allText.match(/(?:Legal [Aa]ddress|Address)[:\\s]+([^\\n]+)/);
            if (addrMatch) result.address = addrMatch[1].trim();

            // Founded / registration date
            const foundMatch = allText.match(/(\\d{2}\\.\\d{2}\\.\\d{4})\\s*\\(/);
            if (foundMatch) result.founded = foundMatch[1];

            // Employees
            const empMatch = allText.match(/Employees[:\\s]+(\\d+)/i);
            if (empMatch) result.employees = empMatch[1];

            // Turnover
            const turnMatch = allText.match(/Turnover[:\\s]+([-\\d\\s,.]+)\\s*(?:EUR|€)/i);
            if (turnMatch) result.turnover = turnMatch[1].trim();

            // Net profit
            const profMatch = allText.match(/Net [Pp]rofit[:\\s]+([-\\d\\s,.]+)\\s*(?:EUR|€)/i);
            if (profMatch) result.net_profit = profMatch[1].trim();

            // Share capital
            const capMatch = allText.match(/Share [Cc]apital[:\\s]+([-\\d\\s,.]+)\\s*(?:EUR|€)/i);
            if (capMatch) result.share_capital = capMatch[1].trim();

            // EMTAK / sector
            const emtakMatch = allText.match(/EMTAK[:\\s]+([\\d]+)/i);
            if (emtakMatch) result.emtak = emtakMatch[1];

            // Phone
            const phoneMatch = allText.match(/\\+372\\s*[\\d\\s]+/);
            if (phoneMatch) result.phone = phoneMatch[0].trim();

            // Website
            const links = document.querySelectorAll('a[href]');
            for (const a of links) {
                const href = a.getAttribute('href') || '';
                if (href.startsWith('http') && !href.includes('ssb.ee') && !href.includes('google')
                    && !href.includes('facebook') && !href.includes('linkedin')
                    && href.length < 100) {
                    result.website = href;
                    break;
                }
            }

            // Description - first substantial paragraph
            const paras = document.querySelectorAll('p, div.description');
            for (const p of paras) {
                const text = p.textContent.trim();
                if (text.length > 100 && !text.includes('cookie') && !text.includes('privacy')) {
                    result.description = text.substring(0, 500);
                    break;
                }
            }

            return result;
        }""")
    except Exception as e:
        log.warning("JS evaluate failed for %s: %s", reg_code, e)
        return None

    if not data or not data.get("name"):
        return None

    return data


def _scrape_financials(page, reg_code: str, name_slug: str) -> list[dict]:
    """Scrape financials page from ssb.ee."""
    url = f"{BASE}/{reg_code}-{name_slug}/financial-assets-forecasts"
    try:
        page.goto(url, timeout=20000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(1.5)
    except Exception as e:
        log.warning("Failed to load financials for %s: %s", reg_code, e)
        return []

    try:
        raw = page.evaluate("""() => {
            const tables = document.querySelectorAll('table');
            const results = [];
            tables.forEach(t => {
                const rows = [];
                t.querySelectorAll('tr').forEach(tr => {
                    const cells = [];
                    tr.querySelectorAll('th, td').forEach(td => cells.push(td.textContent.trim()));
                    if (cells.length > 1) rows.push(cells);
                });
                if (rows.length > 1) results.push(rows);
            });
            // Also try parsing from text if no tables
            if (!results.length) {
                const text = document.body.innerText;
                const yearMatches = [...text.matchAll(/(\\d{4}).*?Turnover.*?([-\\d\\s,.]+)/g)];
            }
            return results;
        }""")
    except Exception:
        return []

    if not raw:
        return []

    financials = []
    for table_rows in raw:
        headers = table_rows[0] if table_rows else []
        years = []
        for h in headers:
            m = re.match(r"^(\d{4})$", h.strip())
            if m:
                years.append((headers.index(h), int(m.group(1))))
        for yi, year_int in years:
            entry = {"year": year_int}
            for row in table_rows[1:]:
                if len(row) <= yi:
                    continue
                label, val = row[0].lower(), row[yi]
                num = _parse_number(val)
                if "turnover" in label or "revenue" in label or "sales" in label:
                    entry["sales_revenue"] = num
                elif "net profit" in label or "net income" in label:
                    entry["net_profit"] = num
                elif "equity" in label:
                    entry["equity"] = num
                elif "assets" in label and "total" in label:
                    entry["total_assets"] = num
            if entry.get("sales_revenue") is not None:
                financials.append(entry)
    return financials


def _parse_number(text: str) -> float | None:
    if not text:
        return None
    cleaned = re.sub(r"[^\d.,-]", "", text.replace(" ", ""))
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _get_emtak_company_list(page, emtak_code: str, page_num: int = 1) -> list[dict]:
    """Get companies from EMTAK search results page."""
    url = f"{BASE}/search-results/companies?emtak_list={emtak_code}"
    if page_num > 1:
        url += f"&page={page_num}"
    try:
        page.goto(url, timeout=25000)
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(2)
    except Exception as e:
        log.warning("Failed to load EMTAK %s page %d: %s", emtak_code, page_num, e)
        return []

    try:
        companies = page.evaluate("""() => {
            const results = [];
            // Look for company links — ssb.ee uses /en/{code}-{name}/ pattern
            const links = document.querySelectorAll('a[href]');
            const seen = new Set();
            for (const a of links) {
                const href = a.getAttribute('href') || '';
                const match = href.match(/\\/en\\/(\\d{7,8})-([A-Z0-9_-]+)/);
                if (match && !seen.has(match[1])) {
                    seen.add(match[1]);
                    const name = a.textContent.trim();
                    if (name && name.length > 1 && name.length < 100) {
                        results.push({reg_code: match[1], slug: match[2], name: name});
                    }
                }
            }
            return results;
        }""")
    except Exception:
        return []

    return companies or []


def scrape(target: int = 500, limit_per_cat: int = 50, max_pages: int = 3,
           headless: bool = True):
    from playwright.sync_api import sync_playwright

    sorted_cats = sorted(EMTAK_CATEGORIES.items(), key=lambda x: x[1].get("priority", 99))

    all_companies = []
    seen_codes = set()
    if DATA_PATH.exists():
        existing = json.loads(DATA_PATH.read_text())
        all_companies.extend(existing)
        seen_codes.update(c.get("reg_code", "") for c in existing)
        log.info("Resuming: %d existing companies (target: %d)", len(existing), target)
    else:
        log.info("Starting fresh (target: %d companies)", target)

    if len(all_companies) >= target:
        log.info("Already at target, nothing to do")
        return all_companies

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
        )
        page = ctx.new_page()

        def _make_context():
            nonlocal ctx, page
            try:
                ctx.close()
            except Exception:
                pass
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                locale="en-US",
            )
            page = ctx.new_page()

        def _safe_scrape(reg_code, name_slug, sector, sub_sector):
            nonlocal ctx, page
            for attempt in range(2):
                try:
                    info = _scrape_company_page(page, reg_code, name_slug)
                    if not info or not info.get("name"):
                        return None
                    financials = _scrape_financials(page, reg_code, name_slug)
                    info["financials"] = financials
                    info["sector"] = sector
                    info["sub_sector"] = sub_sector
                    info["reg_code"] = reg_code
                    info["slug"] = name_slug.lower().replace("-", "_")
                    info["country"] = "EE"
                    return info
                except Exception as e:
                    if attempt == 0:
                        log.warning("    Context crashed, recovering: %s", e)
                        _make_context()
                    else:
                        return None
            return None

        def _save_checkpoint():
            DATA_PATH.parent.mkdir(exist_ok=True)
            DATA_PATH.write_text(json.dumps(all_companies, indent=2, ensure_ascii=False))
            log.info("  Checkpoint: %d companies saved", len(all_companies))

        for emtak_code, cat_cfg in sorted_cats:
            if len(all_companies) >= target:
                break

            sector = cat_cfg["sector"]
            sub_sector = cat_cfg["sub_sector"]
            log.info("EMTAK %s: %s → %s (%d/%d total)",
                     emtak_code, sub_sector, sector, len(all_companies), target)

            cat_count = 0
            for page_num in range(1, max_pages + 1):
                if cat_count >= limit_per_cat or len(all_companies) >= target:
                    break

                try:
                    companies = _get_emtak_company_list(page, emtak_code, page_num)
                except Exception:
                    _make_context()
                    companies = _get_emtak_company_list(page, emtak_code, page_num)

                if not companies:
                    log.info("  Page %d: no companies, moving on", page_num)
                    break

                log.info("  Page %d: %d companies", page_num, len(companies))

                for co in companies:
                    if co["reg_code"] in seen_codes:
                        continue
                    if cat_count >= limit_per_cat or len(all_companies) >= target:
                        break

                    info = _safe_scrape(co["reg_code"], co["slug"], sector, sub_sector)
                    if not info:
                        continue

                    all_companies.append(info)
                    seen_codes.add(co["reg_code"])
                    cat_count += 1

                    if len(all_companies) % 25 == 0:
                        _save_checkpoint()

                time.sleep(0.5)

            log.info("  → %d from EMTAK %s (total: %d)", cat_count, emtak_code, len(all_companies))

        # Must-include companies
        for code in MUST_INCLUDE_CODES:
            if code in seen_codes:
                continue
            log.info("Must-include: %s", code)
            info = _safe_scrape(code, code, "healthcare", "Must-include")
            if info:
                all_companies.append(info)
                seen_codes.add(code)

        browser.close()

    DATA_PATH.parent.mkdir(exist_ok=True)
    DATA_PATH.write_text(json.dumps(all_companies, indent=2, ensure_ascii=False))
    log.info("Done: %d Estonian companies saved to %s", len(all_companies), DATA_PATH)
    return all_companies


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=500, help="total companies to scrape")
    ap.add_argument("--limit-per-cat", type=int, default=50, help="max per EMTAK category")
    ap.add_argument("--pages", type=int, default=3, help="max listing pages per category")
    ap.add_argument("--headless", default="true", help="true/false")
    args = ap.parse_args()
    scrape(target=args.target, limit_per_cat=args.limit_per_cat,
           max_pages=args.pages, headless=args.headless.lower() != "false")
