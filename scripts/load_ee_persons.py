"""Load persons from Baltic company data into pehero.persons + person_company_links.

Sources:
  - data/ee_owners.json  → EE shareholders + beneficial owners (519 persons)
  - data/lt_companies.json → LT company managers/directors (2000+ persons)

Usage:
    python -m scripts.load_ee_persons              # load into DB
    python -m scripts.load_ee_persons --dry-run     # preview counts
    python -m scripts.load_ee_persons --fresh       # truncate then reload
    python -m scripts.load_ee_persons --rich data/ee_rich.json  # merge wealth data
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

from db import connect


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EE_OWNERS_PATH = DATA_DIR / "ee_owners.json"
LT_COMPANIES_PATH = DATA_DIR / "lt_companies.json"


def _normalize_name(raw: str) -> str:
    name = raw.strip()
    name = re.sub(r"^Omanikukonto:\s*", "", name, flags=re.IGNORECASE)
    name = name.strip()
    if name.isupper() or name.islower():
        name = name.title()
    return name


def _slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    return re.sub(r"[-\s]+", "-", s)


def _parse_ee_persons(data: list[dict]) -> dict[str, dict]:
    """Parse EE shareholders + beneficial owners."""
    persons: dict[str, dict] = {}
    for rec in data:
        if "error" in rec and not rec.get("shareholders"):
            continue
        company_id = rec.get("id")
        company_name = rec.get("db_name", rec.get("name", ""))
        reg_code = rec.get("reg_code")

        for sh in rec.get("shareholders", []):
            name = _normalize_name(sh["name"])
            if not name or len(name) < 3:
                continue
            if re.search(r"\b(OÜ|AS|MTÜ|SA|TÜ|UÜ|FIE)\b", name, re.IGNORECASE):
                continue
            p = persons.setdefault(name, {"companies": [], "country": "EE"})
            p["companies"].append({
                "company_id": company_id,
                "company_name": company_name,
                "reg_code": reg_code,
                "role": "shareholder",
                "stake_pct": sh.get("pct_num"),
                "control_desc": None,
            })

        for bo in rec.get("beneficial_owners", []):
            name = _normalize_name(bo["name"])
            if not name or len(name) < 3:
                continue
            p = persons.setdefault(name, {"companies": [], "country": "EE"})
            p["companies"].append({
                "company_id": company_id,
                "company_name": company_name,
                "reg_code": reg_code,
                "role": "beneficial_owner",
                "stake_pct": None,
                "control_desc": bo.get("control"),
            })

    return persons


def _parse_lt_managers(data: list[dict]) -> dict[str, dict]:
    """Parse LT company managers/directors."""
    persons: dict[str, dict] = {}

    # Build slug→id lookup for LT companies in DB
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, slug, name FROM pehero.companies WHERE country = 'LT'")
        lt_companies = {}
        for row in cur.fetchall():
            lt_companies[row[1]] = {"id": row[0], "name": row[2]}

    for rec in data:
        raw_mgr = rec.get("manager", "")
        if not raw_mgr:
            continue

        # Clean "Name, title \n More >" pattern
        name = re.split(r",\s*(?:direktorius|direktorė|vadovas|vadovė|generalinis|gen\.|įkūrėjas|steigėjas|pirmininkas|pirmininkė)",
                        raw_mgr, flags=re.IGNORECASE)[0].strip()
        name = re.split(r"\n", name)[0].strip()
        name = re.sub(r"\s*More\s*›.*$", "", name).strip()

        if not name or len(name) < 3 or len(name) > 80:
            continue
        # Skip if looks like a company name
        if re.search(r"\b(UAB|AB|VŠĮ|MB|IĮ|KŪB)\b", name, re.IGNORECASE):
            continue

        name = _normalize_name(name)
        company_slug = rec.get("slug", "")
        company_name = rec.get("name", "")
        reg_code = rec.get("reg_code")

        db_company = lt_companies.get(company_slug, {})
        company_id = db_company.get("id")

        p = persons.setdefault(name, {"companies": [], "country": "LT"})
        p["companies"].append({
            "company_id": company_id,
            "company_name": company_name,
            "reg_code": reg_code,
            "role": "director",
            "stake_pct": None,
            "control_desc": "vadovas / direktorius",
        })

    return persons


def _load_rich(path: str | None) -> dict[str, dict]:
    """Load wealth data keyed by normalized name."""
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        print(f"  wealth file {p} not found, skipping")
        return {}
    data = json.loads(p.read_text())
    rich: dict[str, dict] = {}
    for entry in data:
        name = _normalize_name(entry.get("name", ""))
        if name and entry.get("wealth_eur"):
            rich[name] = {
                "wealth_eur": entry.get("wealth_eur"),
                "wealth_rank": entry.get("rank"),
                "wealth_source": entry.get("source", "Äripäev"),
            }
    if rich:
        print(f"  loaded {len(rich)} wealth entries from {p.name}")
    return rich


def load(dry_run: bool = False, fresh: bool = False, rich_path: str | None = None):
    # Parse all sources
    persons: dict[str, dict] = {}

    if EE_OWNERS_PATH.exists():
        ee_data = json.loads(EE_OWNERS_PATH.read_text())
        ee_persons = _parse_ee_persons(ee_data)
        persons.update(ee_persons)
        print(f"EE: {len(ee_persons)} persons from {len(ee_data)} company records")

    if LT_COMPANIES_PATH.exists():
        lt_data = json.loads(LT_COMPANIES_PATH.read_text())
        lt_persons = _parse_lt_managers(lt_data)
        # Merge without overwriting EE entries
        for name, info in lt_persons.items():
            if name in persons:
                persons[name]["companies"].extend(info["companies"])
            else:
                persons[name] = info
        print(f"LT: {len(lt_persons)} persons from {len(lt_data)} company records")

    rich = _load_rich(rich_path)

    # Derive sector exposure from linked companies
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, sector FROM pehero.companies")
        company_sectors = {r[0]: r[1] for r in cur.fetchall() if r[1]}

    for name, info in persons.items():
        sectors = set()
        for link in info["companies"]:
            cid = link["company_id"]
            if cid and cid in company_sectors:
                sectors.add(company_sectors[cid])
        info["sector_exposure"] = sorted(sectors)

    print(f"\ntotal: {len(persons)} unique persons")
    if dry_run:
        top = sorted(persons.items(), key=lambda x: len(x[1]["companies"]), reverse=True)[:20]
        for name, info in top:
            w = rich.get(name)
            wealth_str = f"  €{w['wealth_eur']:,.0f} (#{w['wealth_rank']})" if w and w.get("wealth_eur") else ""
            print(f"  {name} ({info['country']}): {len(info['companies'])} companies{wealth_str}")
        return

    with connect() as conn, conn.cursor() as cur:
        if fresh:
            print("  truncating persons + person_company_links…")
            cur.execute("TRUNCATE pehero.person_company_links, pehero.persons CASCADE")

        loaded = 0
        for name, info in persons.items():
            slug = _slugify(name)
            if not slug:
                continue

            w = rich.get(name, {})
            cur.execute("""
                INSERT INTO pehero.persons (name, slug, country, wealth_eur, wealth_rank, wealth_source, sector_exposure)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (slug) DO UPDATE SET
                    wealth_eur = COALESCE(EXCLUDED.wealth_eur, pehero.persons.wealth_eur),
                    wealth_rank = COALESCE(EXCLUDED.wealth_rank, pehero.persons.wealth_rank),
                    wealth_source = COALESCE(EXCLUDED.wealth_source, pehero.persons.wealth_source),
                    sector_exposure = EXCLUDED.sector_exposure
                RETURNING id
            """, (name, slug, info["country"],
                  w.get("wealth_eur"), w.get("wealth_rank"), w.get("wealth_source"),
                  info["sector_exposure"]))
            person_id = cur.fetchone()[0]

            for link in info["companies"]:
                cur.execute("""
                    INSERT INTO pehero.person_company_links
                        (person_id, company_id, company_name, reg_code, role, stake_pct, control_desc)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (person_id, company_name, role) DO UPDATE SET
                        stake_pct = COALESCE(EXCLUDED.stake_pct, pehero.person_company_links.stake_pct),
                        control_desc = COALESCE(EXCLUDED.control_desc, pehero.person_company_links.control_desc)
                """, (person_id, link["company_id"], link["company_name"],
                      link["reg_code"], link["role"], link["stake_pct"], link["control_desc"]))

            loaded += 1

        conn.commit()
        print(f"  loaded {loaded} persons with links")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--rich", type=str, default=None, help="Path to ee_rich.json wealth data")
    args = ap.parse_args()
    load(dry_run=args.dry_run, fresh=args.fresh, rich_path=args.rich)
