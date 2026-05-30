"""Sync PEHero companies + LP CRM to Pipedrive.

Pushes companies (as Organizations + Deals) and investors (as Persons + Deals)
to Pipedrive. Uses pipedrive_sync table to track mappings and skip unchanged.

Usage:
    python -m scripts.sync_pipedrive --push           # push all to Pipedrive
    python -m scripts.sync_pipedrive --push --country LT  # only Lithuanian companies
    python -m scripts.sync_pipedrive --push --lps     # sync LP CRM
    python -m scripts.sync_pipedrive --dry-run        # preview, no API calls
    python -m scripts.sync_pipedrive --setup          # create pipelines + custom fields
"""

from __future__ import annotations

import argparse
import json
import logging

from db import connect, fetch_all, fetch_one
from tools.pipedrive import (
    ensure_pipelines, create_organization, create_deal,
    create_person, create_activity, sync_hash,
    search_organizations, update_deal,
)

log = logging.getLogger(__name__)


DEAL_STAGE_TO_PD = {
    "sourced": "Sourced",
    "screened": "Screened",
    "outreach": "Outreach",
    "meeting": "Meeting",
    "loi": "LOI / Term Sheet",
    "dd": "Due Diligence",
    "ic": "IC Approval",
    "closing": "Closing",
}

LP_STAGE_TO_PD = {
    "cold": "Prospect",
    "qualified": "Qualified",
    "meeting": "Intro Meeting",
    "dd": "Due Diligence",
    "committed": "Soft Commit",
    "closed": "Funded",
    "passed": "Passed",
}


def setup_pipelines():
    pipelines = ensure_pipelines()
    log.info("Pipelines ready:")
    for key, val in pipelines.items():
        log.info("  %s: pipeline_id=%s, stages=%s",
                 key, val["pipeline_id"], list(val["stages"].keys()))
    return pipelines


def push_companies(country: str | None = None, dry_run: bool = False):
    sql = "SELECT * FROM pehero.companies WHERE deal_stage IS NOT NULL"
    params: list = []
    if country:
        sql += " AND country = %s"
        params.append(country)
    sql += " ORDER BY revenue_ltm DESC NULLS LAST LIMIT 500"

    companies = fetch_all(sql, tuple(params) if params else None)
    log.info("Found %d companies to sync", len(companies))

    if dry_run:
        for c in companies[:10]:
            log.info("  %s | %s | %s | rev=%s | stage=%s",
                     c["slug"][:25], c["country"], c["sector"],
                     f"€{float(c['revenue_ltm']):,.0f}" if c["revenue_ltm"] else "N/A",
                     c["deal_stage"])
        return

    pipelines = ensure_pipelines()
    ds = pipelines["deal_sourcing"]
    synced = 0
    skipped = 0

    for c in companies:
        existing = fetch_one(
            "SELECT pipedrive_id FROM pehero.pipedrive_sync "
            "WHERE entity_type = 'company' AND pehero_id = %s",
            (c["id"],),
        )

        fields_to_hash = {
            "name": c["name"], "revenue": str(c["revenue_ltm"]),
            "stage": c["deal_stage"], "sector": c["sector"],
        }
        new_hash = sync_hash(fields_to_hash)

        if existing:
            old = fetch_one(
                "SELECT sync_hash FROM pehero.pipedrive_sync "
                "WHERE entity_type = 'company' AND pehero_id = %s",
                (c["id"],),
            )
            if old and old["sync_hash"] == new_hash:
                skipped += 1
                continue

            pd_stage = DEAL_STAGE_TO_PD.get(c["deal_stage"], "Sourced")
            stage_id = ds["stages"].get(pd_stage, list(ds["stages"].values())[0])
            update_deal(existing["pipedrive_id"], stage_id=stage_id)

            with connect() as conn, conn.cursor() as cur:
                cur.execute(
                    "UPDATE pehero.pipedrive_sync SET sync_hash = %s, last_synced = now() "
                    "WHERE entity_type = 'company' AND pehero_id = %s",
                    (new_hash, c["id"]),
                )
                conn.commit()
            synced += 1
            continue

        org_id = create_organization(
            name=c["name"],
            address={"locality": c["hq_city"], "country": c["country"]} if c["hq_city"] else None,
        )

        pd_stage = DEAL_STAGE_TO_PD.get(c["deal_stage"], "Sourced")
        stage_id = ds["stages"].get(pd_stage, list(ds["stages"].values())[0])

        deal_id = create_deal(
            title=c["name"],
            pipeline_id=ds["pipeline_id"],
            stage_id=stage_id,
            org_id=org_id,
            value=float(c["enterprise_value"]) if c["enterprise_value"] else None,
        )

        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pehero.pipedrive_sync "
                "(entity_type, pehero_id, pipedrive_id, pipedrive_type, sync_hash) "
                "VALUES ('company', %s, %s, 'deal', %s)",
                (c["id"], deal_id, new_hash),
            )
            conn.commit()

        synced += 1
        if synced % 50 == 0:
            log.info("  Synced %d companies...", synced)

    log.info("Done: %d synced, %d skipped (unchanged)", synced, skipped)


def push_lps(dry_run: bool = False):
    lps = fetch_all(
        "SELECT * FROM pehero.investor_crm ORDER BY commitment_size DESC NULLS LAST"
    )
    log.info("Found %d LPs to sync", len(lps))

    if dry_run:
        for lp in lps[:10]:
            log.info("  %s | %s | %s | commit=%s | stage=%s",
                     lp["name"][:25], lp["firm"] or "", lp["lp_type"],
                     f"€{float(lp['commitment_size']):,.0f}" if lp["commitment_size"] else "N/A",
                     lp["stage"])
        return

    pipelines = ensure_pipelines()
    lp_pl = pipelines["lp_fundraising"]
    synced = 0

    for lp in lps:
        existing = fetch_one(
            "SELECT pipedrive_id FROM pehero.pipedrive_sync "
            "WHERE entity_type = 'investor' AND pehero_id = %s",
            (lp["id"],),
        )
        if existing:
            synced += 1
            continue

        org_id = create_organization(name=lp["firm"] or lp["name"])

        person_id = create_person(
            name=lp["name"],
            org_id=org_id,
            emails=[{"label": "work", "value": lp["email"], "primary": True}] if lp["email"] else None,
        )

        pd_stage = LP_STAGE_TO_PD.get(lp["stage"], "Prospect")
        stage_id = lp_pl["stages"].get(pd_stage, list(lp_pl["stages"].values())[0])

        deal_id = create_deal(
            title=f"LP: {lp['name']} ({lp['firm'] or 'Independent'})",
            pipeline_id=lp_pl["pipeline_id"],
            stage_id=stage_id,
            org_id=org_id,
            person_id=person_id,
            value=float(lp["commitment_size"]) if lp["commitment_size"] else None,
        )

        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pehero.pipedrive_sync "
                "(entity_type, pehero_id, pipedrive_id, pipedrive_type, sync_hash) "
                "VALUES ('investor', %s, %s, 'deal', %s)",
                (lp["id"], deal_id, sync_hash({"name": lp["name"], "stage": lp["stage"]})),
            )
            conn.commit()

        synced += 1

    log.info("Done: %d LPs synced", synced)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true", help="push to Pipedrive")
    ap.add_argument("--lps", action="store_true", help="sync LP CRM (default: companies)")
    ap.add_argument("--country", type=str, default=None, help="filter by country code")
    ap.add_argument("--dry-run", action="store_true", help="preview only")
    ap.add_argument("--setup", action="store_true", help="create pipelines and stages")
    args = ap.parse_args()

    if args.setup:
        setup_pipelines()
    elif args.push:
        if args.lps:
            push_lps(dry_run=args.dry_run)
        else:
            push_companies(country=args.country, dry_run=args.dry_run)
    else:
        ap.print_help()
