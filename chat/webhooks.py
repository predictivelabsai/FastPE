"""Pipedrive webhook receiver — handles deal/person/activity changes."""

from __future__ import annotations

import json
import logging

from starlette.requests import Request
from starlette.responses import JSONResponse

from app import rt
from db import connect, fetch_one

log = logging.getLogger(__name__)

STAGE_TO_DEAL_STAGE = {
    "Sourced": "sourced",
    "Screened": "screened",
    "Outreach": "outreach",
    "Meeting": "meeting",
    "LOI / Term Sheet": "loi",
    "Due Diligence": "dd",
    "IC Approval": "ic",
    "Closing": "closing",
}

LP_STAGE_MAP = {
    "Prospect": "cold",
    "Qualified": "qualified",
    "Intro Meeting": "meeting",
    "Due Diligence": "dd",
    "Soft Commit": "committed",
    "Funded": "closed",
    "Passed": "passed",
}


def _find_pehero_id(pipedrive_id: int, pipedrive_type: str) -> int | None:
    row = fetch_one(
        "SELECT pehero_id, entity_type FROM pehero.pipedrive_sync "
        "WHERE pipedrive_id = %s AND pipedrive_type = %s",
        (pipedrive_id, pipedrive_type),
    )
    return row["pehero_id"] if row else None


def _handle_deal_change(data: dict, previous: dict | None):
    deal_id = data.get("id")
    if not deal_id:
        return

    pehero_id = _find_pehero_id(deal_id, "deal")
    if not pehero_id:
        log.debug("No PEHero mapping for Pipedrive deal %d", deal_id)
        return

    stage_id = data.get("stage_id")
    status = data.get("status")

    if previous and "stage_id" in (previous or {}):
        stage_name = data.get("stage_name", "")
        new_stage = STAGE_TO_DEAL_STAGE.get(stage_name) or LP_STAGE_MAP.get(stage_name)
        if new_stage:
            with connect() as conn, conn.cursor() as cur:
                cur.execute(
                    "UPDATE pehero.companies SET deal_stage = %s WHERE id = %s",
                    (new_stage, pehero_id),
                )
                conn.commit()
            log.info("Synced deal %d → company %d stage=%s", deal_id, pehero_id, new_stage)

    if status in ("won", "lost"):
        new_stage = "closed" if status == "won" else "passed"
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE pehero.companies SET deal_stage = %s WHERE id = %s",
                (new_stage, pehero_id),
            )
            conn.commit()
        log.info("Deal %d %s → company %d stage=%s", deal_id, status, pehero_id, new_stage)


def _handle_activity_create(data: dict):
    deal_id = data.get("deal_id")
    if not deal_id:
        return

    pehero_id = _find_pehero_id(deal_id, "deal")
    if not pehero_id:
        return

    activity_type = data.get("type", "")
    if activity_type in ("call", "meeting", "email"):
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE pehero.investor_crm SET last_touch = now() WHERE id = %s",
                (pehero_id,),
            )
            conn.commit()
        log.info("Activity %s on deal %d → updated last_touch for %d",
                 activity_type, deal_id, pehero_id)


@rt("/api/webhooks/pipedrive", methods=["POST"])
async def pipedrive_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    meta = payload.get("meta", {})
    action = meta.get("action", "")
    entity = meta.get("entity", "")
    data = payload.get("data", {})
    previous = payload.get("previous")

    log.info("Pipedrive webhook: %s.%s id=%s", entity, action, meta.get("entity_id"))

    if entity == "deal" and action == "change":
        _handle_deal_change(data, previous)
    elif entity == "activity" and action == "create":
        _handle_activity_create(data)

    return JSONResponse({"ok": True})
