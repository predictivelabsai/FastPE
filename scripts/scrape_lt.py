"""One-off scraper: Lithuanian companies from rekvizitai.vz.lt → data/lt_companies.json.

Usage:
    python -m scripts.scrape_lt                   # scrape ~120 companies
    python -m scripts.scrape_lt --limit 5         # quick test with 5 per category
    python -m scripts.scrape_lt --headless false   # visible browser for debugging

Requires: playwright (already installed for screenshot capture).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from pathlib import Path

log = logging.getLogger(__name__)

CATEGORIES = {
    "health_care_institutions": "healthcare",
    "real_estate": "business_services",
    "insurance": "financial_services",
    "motor_transport_services": "industrials",
    "veterinary_medicine": "healthcare",
    "odonthology_services": "healthcare",
}

CATEGORY_SUBSECTORS = {
    "health_care_institutions": "Health care institutions",
    "real_estate": "Real estate development",
    "insurance": "Insurance",
    "motor_transport_services": "Logistics services",
    "veterinary_medicine": "Veterinary clinics",
    "odonthology_services": "Dental clinics",
}

# Specific companies to always include (slug → category override)
MUST_INCLUDE = [
    "gyvunu_ligonine",                      # DR VET
    "northway_medicinos_centras",           # Northway
    "kardiolita",                            # Meliva Kardiolita (Vilnius)
    "kardiolitos_klinikos",                 # Kardiolita Kaunas variant
]

BASE = "https://rekvizitai.vz.lt/en"


def _parse_euros(text: str) -> float | None:
    """Parse '3 796 775 €' or '-578 474 €' → float."""
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
    """'3 years 7 months 4 days' → founded_year."""
    m = re.search(r"(\d+)\s*year", age_text)
    if m:
        from datetime import date
        return date.today().year - int(m.group(1))
    return None


def _parse_city(address: str) -> str | None:
    if not address:
        return None
    parts = [p.strip() for p in address.split(",")]
    for p in reversed(parts):
        cleaned = re.sub(r"LT-\d+\s*", "", p).strip()
        if cleaned and not cleaned[0].isdigit():
            return cleaned
    return None


def _scrape_company_page(page, slug: str) -> dict | None:
    """Navigate to company page, extract structured data."""
    url = f"{BASE}/company/{slug}/"
    try:
        page.goto(url, timeout=15000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(0.5)
    except Exception as e:
        log.warning("Failed to load %s: %s", url, e)
        return None

    try:
        data = page.evaluate("""() => {
            const result = {};

            // Company name from h1
            const h1 = document.querySelector('h1');
            result.name = h1 ? h1.textContent.trim() : '';

            // All table rows as key-value pairs — rows have 3 cells (icon, label, value)
            const main = document.querySelector('main') || document.body;
            const tables = main.querySelectorAll('table');
            tables.forEach(t => {
                if (t.closest('dialog') || t.closest('[role="dialog"]')) return;
                t.querySelectorAll('tr').forEach(tr => {
                    const cells = tr.querySelectorAll('td');
                    if (cells.length >= 2) {
                        // Last two non-empty cells are key-value
                        const texts = [...cells].map(c => c.textContent.trim());
                        let key = '', val = '';
                        if (cells.length === 2) { key = texts[0]; val = texts[1]; }
                        else if (cells.length === 3) { key = texts[1]; val = texts[2]; }
                        else { key = texts[texts.length - 2]; val = texts[texts.length - 1]; }
                        if (key && key.length < 80) result[key] = val;
                    }
                });
            });

            // Try to grab revenue and profit from the summary boxes
            const allText = document.body.innerText;
            const revMatch = allText.match(/Sales revenue[\\s\\n]+([-\\d\\s]+\\s*€)\\s*\\((\\d{4})/);
            if (revMatch) {
                result['_sales_revenue'] = revMatch[1];
                result['_sales_year'] = revMatch[2];
            }
            const profitMatch = allText.match(/Net (?:profit|loss)[\\s\\n]+([-\\d\\s]+\\s*€)\\s*\\((\\d{4})/i);
            if (profitMatch) {
                result['_net_profit'] = profitMatch[1];
                result['_profit_year'] = profitMatch[2];
            }

            // Description paragraph
            const paragraphs = document.querySelectorAll('p');
            for (const p of paragraphs) {
                const text = p.textContent.trim();
                if (text.length > 80 && text.includes('was founded')) {
                    result['_description'] = text;
                    break;
                }
            }

            // Categories
            const catLinks = document.querySelectorAll('a[href*="/en/companies/"]');
            const cats = [];
            catLinks.forEach(a => {
                const t = a.textContent.trim();
                if (t && t.length > 2 && !['Company search','Company databases'].includes(t)) {
                    cats.push(t);
                }
            });
            result['_categories'] = cats.join('; ');

            return result;
        }""")
    except Exception as e:
        log.warning("    JS evaluate failed for %s: %s", slug, e)
        return None

    if not data or not data.get("name"):
        return None

    return {
        "slug": slug,
        "name": data.get("name", ""),
        "reg_code": data.get("Registration code", ""),
        "vat": data.get("VAT", ""),
        "share_capital": data.get("Share capital", ""),
        "company_age": data.get("Company age", ""),
        "manager": data.get("Manager", ""),
        "address": data.get("Address", ""),
        "phone": data.get("Phone", ""),
        "website": data.get("Website", ""),
        "employees_text": data.get("Employees", ""),
        "avg_salary": data.get("Average salary", ""),
        "credit_risk": data.get("Credit Risk", ""),
        "sales_revenue": data.get("_sales_revenue", ""),
        "sales_year": data.get("_sales_year", ""),
        "net_profit": data.get("_net_profit", ""),
        "profit_year": data.get("_profit_year", ""),
        "description": data.get("_description", ""),
        "categories": data.get("_categories", ""),
    }


def _scrape_financials(page, slug: str) -> list[dict]:
    """Navigate to financials page, extract multi-year table."""
    url = f"{BASE}/company/{slug}/turnover/"
    try:
        page.goto(url, timeout=15000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(0.5)
    except Exception as e:
        log.warning("Failed to load financials for %s: %s", slug, e)
        return []

    raw = page.evaluate("""() => {
        const tables = document.querySelectorAll('table');
        if (!tables.length) return [];
        const t = tables[0];
        const rows = [];
        t.querySelectorAll('tr').forEach(tr => {
            const cells = [];
            tr.querySelectorAll('th, td').forEach(td => cells.push(td.textContent.trim()));
            if (cells.length > 1) rows.push(cells);
        });
        return rows;
    }""")

    if not raw or len(raw) < 2:
        return []

    headers = raw[0]
    years = [h for h in headers[1:] if re.match(r"\d{4}", h)]
    financials = []
    for year in years:
        yi = headers.index(year)
        entry = {"year": int(year)}
        for row in raw[1:]:
            if len(row) <= yi:
                continue
            label = row[0]
            val = row[yi]
            if "Sales revenue" in label:
                entry["sales_revenue"] = _parse_euros(val)
            elif "Net profit" in label and "margin" not in label.lower():
                entry["net_profit"] = _parse_euros(val)
            elif "Profit (loss) before taxes" in label and "margin" not in label.lower():
                entry["profit_before_tax"] = _parse_euros(val)
            elif "Equity capital" in label:
                entry["equity"] = _parse_euros(val)
            elif "Amounts payable" in label or "liabilities" in label.lower():
                entry["liabilities"] = _parse_euros(val)
            elif "Non-current assets" in label:
                entry["non_current_assets"] = _parse_euros(val)
            elif "Current assets" in label:
                entry["current_assets"] = _parse_euros(val)
        financials.append(entry)

    return financials


def _get_category_slugs(page, category_slug: str, limit: int = 30) -> list[str]:
    """Get company slugs from a category listing page."""
    url = f"{BASE}/companies/{category_slug}/"
    try:
        page.goto(url, timeout=15000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(0.5)
    except Exception as e:
        log.warning("Failed to load category %s: %s", category_slug, e)
        return []

    slugs = page.evaluate("""() => {
        const items = document.querySelectorAll('a[href*="/en/company/"]');
        const result = [];
        const seen = new Set();
        const skip = ['/manager/','/turnover/','/report/','/credit-risk/',
                      '/number-of-employees/','/salary/','/legal-entity/',
                      '/tenders/','/trademarks/','/sustainability/','/paid-taxes/'];
        items.forEach(a => {
            const href = a.getAttribute('href');
            const text = a.textContent.trim();
            if (href && text && text.length > 2 && !seen.has(href)
                && !skip.some(s => href.includes(s))) {
                seen.add(href);
                const slug = href.split('/company/')[1]?.replace(/\\/$/, '');
                if (slug) result.push(slug);
            }
        });
        return result;
    }""")

    return slugs[:limit]


def scrape(limit_per_cat: int = 20, headless: bool = True):
    from playwright.sync_api import sync_playwright

    out_path = Path(__file__).resolve().parent.parent / "data" / "lt_companies.json"
    all_companies = []
    seen_slugs = set()

    # Resume from existing data if available
    if out_path.exists():
        existing = json.loads(out_path.read_text())
        all_companies.extend(existing)
        seen_slugs.update(c["slug"] for c in existing)
        log.info("Resuming: loaded %d existing companies", len(existing))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
        )
        # Pre-set Cookiebot consent cookie to skip the dialog entirely
        ctx.add_cookies([{
            "name": "CookieConsent",
            "value": "{stamp:%27-1%27%2Cnecessary:true%2Cpreferences:true%2Cstatistics:true%2Cmarketing:true%2Cmethod:%27explicit%27%2Cver:1}",
            "domain": ".rekvizitai.vz.lt",
            "path": "/",
        }])
        page = ctx.new_page()

        def _make_context():
            nonlocal ctx, page
            try:
                ctx.close()
            except Exception:
                pass
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
            )
            ctx.add_cookies([{
                "name": "CookieConsent",
                "value": "{stamp:%27-1%27%2Cnecessary:true%2Cpreferences:true%2Cstatistics:true%2Cmarketing:true%2Cmethod:%27explicit%27%2Cver:1}",
                "domain": ".rekvizitai.vz.lt",
                "path": "/",
            }])
            page = ctx.new_page()

        def _safe_scrape(slug, sector, sub_sector):
            """Scrape a company with automatic context recovery on crash."""
            nonlocal ctx, page
            for attempt in range(2):
                try:
                    info = _scrape_company_page(page, slug)
                    if not info or not info["name"]:
                        return None
                    financials = _scrape_financials(page, slug)
                    info["financials"] = financials
                    info["sector"] = sector
                    info["sub_sector"] = sub_sector
                    return info
                except Exception as e:
                    if attempt == 0:
                        log.warning("    Context crashed, recovering: %s", e)
                        _make_context()
                    else:
                        log.warning("    Failed after retry: %s", e)
                        return None
            return None

        for cat_slug, sector in CATEGORIES.items():
            sub_sector = CATEGORY_SUBSECTORS[cat_slug]
            log.info("Scraping category: %s → %s", cat_slug, sector)
            try:
                slugs = _get_category_slugs(page, cat_slug, limit=limit_per_cat + 10)
            except Exception:
                _make_context()
                slugs = _get_category_slugs(page, cat_slug, limit=limit_per_cat + 10)
            log.info("  Found %d company slugs", len(slugs))

            count = 0
            for slug in slugs:
                if slug in seen_slugs:
                    continue
                if count >= limit_per_cat:
                    break

                log.info("  [%d/%d] Scraping %s", count + 1, limit_per_cat, slug)
                info = _safe_scrape(slug, sector, sub_sector)
                if not info:
                    log.warning("    Skipped (no data)")
                    continue

                all_companies.append(info)
                seen_slugs.add(slug)
                count += 1

        # Must-include companies (if not already scraped)
        for slug in MUST_INCLUDE:
            if slug in seen_slugs:
                continue
            log.info("Scraping must-include: %s", slug)
            info = _safe_scrape(slug, "healthcare", "Health care institutions")
            if info:
                all_companies.append(info)
                seen_slugs.add(slug)

        browser.close()

    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(all_companies, indent=2, ensure_ascii=False))
    log.info("Wrote %d companies to %s", len(all_companies), out_path)
    return all_companies


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20, help="companies per category")
    ap.add_argument("--headless", default="true", help="true/false")
    args = ap.parse_args()
    scrape(limit_per_cat=args.limit, headless=args.headless.lower() != "false")
