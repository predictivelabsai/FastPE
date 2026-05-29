"""Batch scraper: Lithuanian companies from rekvizitai.vz.lt → data/lt_companies.json.

Reads categories from config/sources.yaml. Supports pagination to reach 1000+ companies.
Resumes from existing data automatically. Recovers from browser crashes.

Usage:
    python -m scripts.scrape_lt                        # scrape all categories, default limits
    python -m scripts.scrape_lt --target 1000          # keep going until 1000 companies
    python -m scripts.scrape_lt --limit-per-cat 50     # max per category
    python -m scripts.scrape_lt --pages 3              # scrape up to 3 pages per category
    python -m scripts.scrape_lt --headless false       # visible browser for debugging
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "sources.yaml"
DATA_PATH = ROOT / "data" / "lt_companies.json"

BASE = "https://rekvizitai.vz.lt/en"


def _load_config() -> dict:
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    return cfg["lithuania"]


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


def _scrape_company_page(page, slug: str) -> dict | None:
    url = f"{BASE}/company/{slug}/"
    try:
        page.goto(url, timeout=20000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(0.5)
    except Exception as e:
        log.warning("Failed to load %s: %s", slug, e)
        return None

    try:
        data = page.evaluate("""() => {
            const result = {};
            const h1 = document.querySelector('h1');
            result.name = h1 ? h1.textContent.trim() : '';

            const main = document.querySelector('main') || document.body;
            const tables = main.querySelectorAll('table');
            tables.forEach(t => {
                if (t.closest('dialog') || t.closest('[role="dialog"]')) return;
                t.querySelectorAll('tr').forEach(tr => {
                    const cells = tr.querySelectorAll('td');
                    if (cells.length >= 2) {
                        const texts = [...cells].map(c => c.textContent.trim());
                        let key = '', val = '';
                        if (cells.length === 2) { key = texts[0]; val = texts[1]; }
                        else if (cells.length === 3) { key = texts[1]; val = texts[2]; }
                        else { key = texts[texts.length - 2]; val = texts[texts.length - 1]; }
                        if (key && key.length < 80) result[key] = val;
                    }
                });
            });

            const allText = document.body.innerText;
            const revMatch = allText.match(/Sales revenue[\\s\\n]+([-\\d\\s]+\\s*€)\\s*\\((\\d{4})/);
            if (revMatch) { result['_sales_revenue'] = revMatch[1]; result['_sales_year'] = revMatch[2]; }
            const profitMatch = allText.match(/Net (?:profit|loss)[\\s\\n]+([-\\d\\s]+\\s*€)\\s*\\((\\d{4})/i);
            if (profitMatch) { result['_net_profit'] = profitMatch[1]; result['_profit_year'] = profitMatch[2]; }

            const paragraphs = document.querySelectorAll('p');
            for (const p of paragraphs) {
                const text = p.textContent.trim();
                if (text.length > 80 && text.includes('was founded')) { result['_description'] = text; break; }
            }

            const catLinks = document.querySelectorAll('a[href*="/en/companies/"]');
            const cats = [];
            catLinks.forEach(a => {
                const t = a.textContent.trim();
                if (t && t.length > 2 && !['Company search','Company databases'].includes(t)) cats.push(t);
            });
            result['_categories'] = cats.join('; ');
            return result;
        }""")
    except Exception as e:
        log.warning("JS evaluate failed for %s: %s", slug, e)
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
    url = f"{BASE}/company/{slug}/turnover/"
    try:
        page.goto(url, timeout=20000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(0.5)
    except Exception as e:
        log.warning("Failed to load financials for %s: %s", slug, e)
        return []

    try:
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
    except Exception:
        return []

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
            label, val = row[0], row[yi]
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


def _get_category_slugs(page, category_slug: str, page_num: int = 1) -> list[str]:
    """Get company slugs from a category listing page."""
    url = f"{BASE}/companies/{category_slug}/"
    if page_num > 1:
        url = f"{BASE}/companies/{category_slug}/{page_num}/"
    try:
        page.goto(url, timeout=20000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(0.5)
    except Exception as e:
        log.warning("Failed to load category %s page %d: %s", category_slug, page_num, e)
        return []

    try:
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
    except Exception:
        return []

    return slugs


def scrape(target: int = 1000, limit_per_cat: int = 80, max_pages: int = 5,
           headless: bool = True):
    from playwright.sync_api import sync_playwright

    cfg = _load_config()
    categories = cfg["categories"]
    must_include = cfg.get("must_include", [])

    # Sort categories by priority
    sorted_cats = sorted(categories.items(), key=lambda x: x[1].get("priority", 99))

    # Resume from existing data
    all_companies = []
    seen_slugs = set()
    if DATA_PATH.exists():
        existing = json.loads(DATA_PATH.read_text())
        all_companies.extend(existing)
        seen_slugs.update(c["slug"] for c in existing)
        log.info("Resuming: %d existing companies (target: %d)", len(existing), target)
    else:
        log.info("Starting fresh (target: %d companies)", target)

    if len(all_companies) >= target:
        log.info("Already at target (%d >= %d), nothing to do", len(all_companies), target)
        return all_companies

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
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
            ctx.add_cookies([{
                "name": "CookieConsent",
                "value": "{stamp:%27-1%27%2Cnecessary:true%2Cpreferences:true%2Cstatistics:true%2Cmarketing:true%2Cmethod:%27explicit%27%2Cver:1}",
                "domain": ".rekvizitai.vz.lt",
                "path": "/",
            }])
            page = ctx.new_page()

        def _safe_scrape(slug, sector, sub_sector):
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
                        return None
            return None

        def _save_checkpoint():
            DATA_PATH.parent.mkdir(exist_ok=True)
            DATA_PATH.write_text(json.dumps(all_companies, indent=2, ensure_ascii=False))
            log.info("  Checkpoint: %d companies saved", len(all_companies))

        for cat_slug, cat_cfg in sorted_cats:
            if len(all_companies) >= target:
                break

            sector = cat_cfg["sector"]
            sub_sector = cat_cfg["sub_sector"]
            log.info("Category: %s → %s (%d/%d total)",
                     cat_slug, sector, len(all_companies), target)

            cat_count = 0
            for page_num in range(1, max_pages + 1):
                if cat_count >= limit_per_cat or len(all_companies) >= target:
                    break

                try:
                    slugs = _get_category_slugs(page, cat_slug, page_num)
                except Exception:
                    _make_context()
                    slugs = _get_category_slugs(page, cat_slug, page_num)

                if not slugs:
                    log.info("  Page %d: no companies found, moving to next category", page_num)
                    break

                log.info("  Page %d: %d slugs", page_num, len(slugs))

                for slug in slugs:
                    if slug in seen_slugs:
                        continue
                    if cat_count >= limit_per_cat or len(all_companies) >= target:
                        break

                    info = _safe_scrape(slug, sector, sub_sector)
                    if not info:
                        continue

                    # Filter: only keep companies with revenue data
                    rev = _parse_euros(info.get("sales_revenue", ""))
                    if not rev and not info.get("financials"):
                        continue

                    all_companies.append(info)
                    seen_slugs.add(slug)
                    cat_count += 1

                    if len(all_companies) % 25 == 0:
                        _save_checkpoint()

                # Small delay between pages
                time.sleep(0.5)

            log.info("  → %d companies from %s (total: %d)", cat_count, cat_slug, len(all_companies))

        # Must-include companies
        for slug in must_include:
            if slug in seen_slugs:
                continue
            log.info("Must-include: %s", slug)
            info = _safe_scrape(slug, "healthcare", "Health care institutions")
            if info:
                all_companies.append(info)
                seen_slugs.add(slug)

        browser.close()

    # Final save
    DATA_PATH.parent.mkdir(exist_ok=True)
    DATA_PATH.write_text(json.dumps(all_companies, indent=2, ensure_ascii=False))
    log.info("Done: %d companies saved to %s", len(all_companies), DATA_PATH)
    return all_companies


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=1000, help="total companies to scrape")
    ap.add_argument("--limit-per-cat", type=int, default=80, help="max per category")
    ap.add_argument("--pages", type=int, default=5, help="max pages per category")
    ap.add_argument("--headless", default="true", help="true/false")
    args = ap.parse_args()
    scrape(target=args.target, limit_per_cat=args.limit_per_cat,
           max_pages=args.pages, headless=args.headless.lower() != "false")
