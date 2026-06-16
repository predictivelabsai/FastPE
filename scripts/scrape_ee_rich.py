"""Scrape the Äripäev richest Estonians list.

Uses httpx to fetch the public list page and extract names, ranks, and
estimated wealth figures.

Usage:
    python -m scripts.scrape_ee_rich                     # scrape → data/ee_rich.json
    python -m scripts.scrape_ee_rich --dry-run            # preview, don't write
    python -m scripts.scrape_ee_rich --limit 50           # first N entries
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "ee_rich.json"

RICH_LIST_URL = "https://www.aripaev.ee/rikaste-top"


def _parse_wealth(text: str) -> float | None:
    """Parse wealth string like '1,2 mld €' or '345 mln €' → EUR float."""
    text = text.strip().lower().replace("\xa0", " ").replace(",", ".")
    m = re.search(r"(\d[\d.]*\d|\d)\s*(mld|mln|mil)", text)
    if not m:
        m = re.search(r"(\d[\d.]*\d|\d)", text)
        if not m:
            return None
        try:
            return float(m.group(1))
        except ValueError:
            return None
    try:
        val = float(m.group(1))
    except ValueError:
        return None
    unit = m.group(2)
    if unit == "mld":
        return val * 1_000_000_000
    return val * 1_000_000


def scrape(limit: int | None = None, dry_run: bool = False) -> list[dict]:
    print(f"fetching {RICH_LIST_URL}")
    resp = httpx.get(RICH_LIST_URL, timeout=30, follow_redirects=True,
                     headers={"User-Agent": "PEHero-Research/1.0"})

    if resp.status_code != 200:
        print(f"  HTTP {resp.status_code}, trying Playwright fallback…")
        return _scrape_playwright(limit, dry_run)

    soup = BeautifulSoup(resp.text, "html.parser")
    entries: list[dict] = []

    # Try common table/list patterns on the Äripäev page
    rows = soup.select("table tbody tr") or soup.select(".top-list__item, .rich-list-item, .rating-item")

    if not rows:
        print("  no structured data found via httpx, trying Playwright fallback…")
        return _scrape_playwright(limit, dry_run)

    for row in rows:
        cells = row.find_all("td") if row.name == "tr" else None
        if cells and len(cells) >= 3:
            rank_text = cells[0].get_text(strip=True)
            name = cells[1].get_text(strip=True)
            wealth_text = cells[2].get_text(strip=True)
        else:
            rank_el = row.select_one(".rank, .position, .number")
            name_el = row.select_one(".name, .title, a")
            wealth_el = row.select_one(".wealth, .value, .amount, .sum")
            if not name_el:
                continue
            rank_text = rank_el.get_text(strip=True) if rank_el else ""
            name = name_el.get_text(strip=True)
            wealth_text = wealth_el.get_text(strip=True) if wealth_el else ""

        if not name:
            continue

        rank_match = re.search(r"\d+", rank_text)
        entry = {
            "rank": int(rank_match.group()) if rank_match else len(entries) + 1,
            "name": name,
            "wealth_eur": _parse_wealth(wealth_text),
            "source": "Äripäev 2024",
        }
        entries.append(entry)
        if limit and len(entries) >= limit:
            break

    return _finish(entries, dry_run)


def _scrape_playwright(limit: int | None, dry_run: bool) -> list[dict]:
    """Fallback: use Playwright for JS-rendered content."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  playwright not installed — run: pip install playwright && playwright install chromium")
        return []

    entries: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(RICH_LIST_URL, wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(2000)

        # Try extracting from the rendered page
        rows = page.query_selector_all("table tbody tr") or \
               page.query_selector_all(".top-list__item, .rich-list-item, .rating-item, [class*='list'] [class*='item']")

        for i, row in enumerate(rows):
            text = row.inner_text().strip()
            if not text:
                continue
            parts = re.split(r"\t|\n", text)
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) >= 2:
                rank_match = re.search(r"\d+", parts[0])
                name = parts[1] if rank_match else parts[0]
                wealth_text = parts[2] if len(parts) > 2 else ""
                entries.append({
                    "rank": int(rank_match.group()) if rank_match else i + 1,
                    "name": name,
                    "wealth_eur": _parse_wealth(wealth_text),
                    "source": "Äripäev 2024",
                })
                if limit and len(entries) >= limit:
                    break

        browser.close()

    return _finish(entries, dry_run)


def _finish(entries: list[dict], dry_run: bool) -> list[dict]:
    print(f"  found {len(entries)} entries")
    for e in entries[:10]:
        w = f"€{e['wealth_eur']:,.0f}" if e["wealth_eur"] else "—"
        print(f"  #{e['rank']:>3}  {e['name']:<30}  {w}")

    if dry_run:
        print("  (dry run — not writing)")
    else:
        OUTPUT_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2))
        print(f"  wrote {OUTPUT_PATH}")
    return entries


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    scrape(limit=args.limit, dry_run=args.dry_run)
