"""Pipedrive CRM client — thin httpx wrapper for deals, persons, organizations, activities, notes.

When PIPEDRIVE_API_TOKEN is not set, all functions return stub data so agents
and tests can run without a live Pipedrive account. Set the token in .env to
activate real API calls.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Optional

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field as PydField

from utils.config import settings

log = logging.getLogger(__name__)

_STUB_COUNTER = 1000


def _is_live() -> bool:
    return bool(settings().pipedrive_api_token)


def _base_url() -> str:
    domain = settings().pipedrive_domain or "api"
    return f"https://{domain}.pipedrive.com"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings().pipedrive_api_token}",
        "Content-Type": "application/json",
    }


def _client() -> httpx.Client:
    return httpx.Client(base_url=_base_url(), headers=_headers(), timeout=20.0)


# ── Generic HTTP helpers ──────────────────────────────────────────────

def pd_get(path: str, params: dict | None = None) -> dict:
    if not _is_live():
        return {"success": True, "data": [], "stub": True}
    with _client() as c:
        r = c.get(path, params=params or {})
        r.raise_for_status()
        return r.json()


def pd_post(path: str, data: dict) -> dict:
    if not _is_live():
        global _STUB_COUNTER
        _STUB_COUNTER += 1
        log.info("STUB pd_post %s → id=%d", path, _STUB_COUNTER)
        return {"success": True, "data": {"id": _STUB_COUNTER, **data}, "stub": True}
    with _client() as c:
        r = c.post(path, json=data)
        r.raise_for_status()
        return r.json()


def pd_patch(path: str, data: dict) -> dict:
    if not _is_live():
        log.info("STUB pd_patch %s", path)
        return {"success": True, "data": data, "stub": True}
    with _client() as c:
        r = c.patch(path, json=data)
        r.raise_for_status()
        return r.json()


def pd_delete(path: str) -> bool:
    if not _is_live():
        log.info("STUB pd_delete %s", path)
        return True
    with _client() as c:
        r = c.delete(path)
        r.raise_for_status()
        return True


# ── Pipeline + Stage management ───────────────────────────────────────

DEAL_SOURCING_STAGES = [
    "Sourced", "Screened", "Outreach", "Meeting",
    "LOI / Term Sheet", "Due Diligence", "IC Approval", "Closing",
]

LP_FUNDRAISING_STAGES = [
    "Prospect", "Qualified", "Intro Meeting",
    "Due Diligence", "Soft Commit", "Funded", "Passed",
]

_pipeline_cache: dict[str, dict] = {}


def ensure_pipelines() -> dict[str, dict]:
    """Idempotent: create Deal Sourcing + LP Fundraising pipelines if missing.

    Returns {"deal_sourcing": {"pipeline_id": N, "stages": {"Sourced": M, ...}},
             "lp_fundraising": {...}}
    """
    if _pipeline_cache:
        return _pipeline_cache

    for name, stages_list, key in [
        ("Deal Sourcing", DEAL_SOURCING_STAGES, "deal_sourcing"),
        ("LP Fundraising", LP_FUNDRAISING_STAGES, "lp_fundraising"),
    ]:
        existing = pd_get("/api/v2/pipelines")
        pipeline_id = None
        for p in (existing.get("data") or []):
            if p.get("name") == name:
                pipeline_id = p["id"]
                break

        if not pipeline_id:
            resp = pd_post("/api/v2/pipelines", {"name": name})
            pipeline_id = resp["data"]["id"]

        existing_stages = pd_get("/api/v2/stages", {"pipeline_id": pipeline_id})
        stage_map = {s["name"]: s["id"] for s in (existing_stages.get("data") or [])}

        for stage_name in stages_list:
            if stage_name not in stage_map:
                resp = pd_post("/api/v2/stages", {
                    "name": stage_name,
                    "pipeline_id": pipeline_id,
                })
                stage_map[stage_name] = resp["data"]["id"]

        _pipeline_cache[key] = {"pipeline_id": pipeline_id, "stages": stage_map}

    return _pipeline_cache


# ── Deal CRUD ─────────────────────────────────────────────────────────

def create_deal(title: str, pipeline_id: int, stage_id: int,
                org_id: int | None = None, person_id: int | None = None,
                value: float | None = None, currency: str = "EUR",
                custom_fields: dict | None = None) -> int:
    data: dict[str, Any] = {
        "title": title,
        "pipeline_id": pipeline_id,
        "stage_id": stage_id,
    }
    if org_id:
        data["org_id"] = org_id
    if person_id:
        data["person_id"] = person_id
    if value:
        data["value"] = value
        data["currency"] = currency
    if custom_fields:
        data["custom_fields"] = custom_fields
    resp = pd_post("/api/v2/deals", data)
    return resp["data"]["id"]


def update_deal(deal_id: int, **fields) -> dict:
    resp = pd_patch(f"/api/v2/deals/{deal_id}", fields)
    return resp.get("data", {})


def move_deal_stage(deal_id: int, stage_id: int) -> dict:
    return update_deal(deal_id, stage_id=stage_id)


def search_deals(term: str, limit: int = 10) -> list[dict]:
    resp = pd_get("/api/v2/deals/search", {"term": term, "limit": limit})
    items = resp.get("data", {})
    if isinstance(items, dict):
        items = items.get("items", [])
    return items or []


def get_deal(deal_id: int) -> dict:
    resp = pd_get(f"/api/v2/deals/{deal_id}")
    return resp.get("data", {})


# ── Person CRUD ───────────────────────────────────────────────────────

def create_person(name: str, org_id: int | None = None,
                  emails: list[dict] | None = None,
                  phones: list[dict] | None = None,
                  custom_fields: dict | None = None) -> int:
    data: dict[str, Any] = {"name": name}
    if org_id:
        data["org_id"] = org_id
    if emails:
        data["emails"] = emails
    if phones:
        data["phones"] = phones
    if custom_fields:
        data["custom_fields"] = custom_fields
    resp = pd_post("/api/v2/persons", data)
    return resp["data"]["id"]


def update_person(person_id: int, **fields) -> dict:
    resp = pd_patch(f"/api/v2/persons/{person_id}", fields)
    return resp.get("data", {})


def search_persons(term: str, limit: int = 10) -> list[dict]:
    resp = pd_get("/api/v2/persons/search", {"term": term, "limit": limit})
    items = resp.get("data", {})
    if isinstance(items, dict):
        items = items.get("items", [])
    return items or []


# ── Organization CRUD ─────────────────────────────────────────────────

def create_organization(name: str, address: dict | None = None,
                        custom_fields: dict | None = None) -> int:
    data: dict[str, Any] = {"name": name}
    if address:
        data["address"] = address
    if custom_fields:
        data["custom_fields"] = custom_fields
    resp = pd_post("/api/v2/organizations", data)
    return resp["data"]["id"]


def update_organization(org_id: int, **fields) -> dict:
    resp = pd_patch(f"/api/v2/organizations/{org_id}", fields)
    return resp.get("data", {})


def search_organizations(term: str, limit: int = 10) -> list[dict]:
    resp = pd_get("/api/v2/organizations/search", {"term": term, "limit": limit})
    items = resp.get("data", {})
    if isinstance(items, dict):
        items = items.get("items", [])
    return items or []


# ── Activity CRUD ─────────────────────────────────────────────────────

def create_activity(subject: str, activity_type: str = "task",
                    deal_id: int | None = None,
                    person_id: int | None = None,
                    org_id: int | None = None,
                    note: str = "",
                    due_date: str | None = None,
                    done: bool = False) -> int:
    data: dict[str, Any] = {
        "subject": subject,
        "type": activity_type,
        "done": done,
    }
    if deal_id:
        data["deal_id"] = deal_id
    if person_id:
        data["person_id"] = person_id
    if org_id:
        data["org_id"] = org_id
    if note:
        data["note"] = note
    if due_date:
        data["due_date"] = due_date
    resp = pd_post("/api/v2/activities", data)
    return resp["data"]["id"]


def list_activities(deal_id: int | None = None,
                    person_id: int | None = None,
                    limit: int = 50) -> list[dict]:
    params: dict[str, Any] = {"limit": limit}
    if deal_id:
        params["deal_id"] = deal_id
    if person_id:
        params["person_id"] = person_id
    resp = pd_get("/api/v2/activities", params)
    return resp.get("data", []) or []


# ── Notes (v1 only) ──────────────────────────────────────────────────

def create_note(content_html: str, deal_id: int | None = None,
                person_id: int | None = None,
                org_id: int | None = None) -> int:
    data: dict[str, Any] = {"content": content_html}
    if deal_id:
        data["deal_id"] = deal_id
    if person_id:
        data["person_id"] = person_id
    if org_id:
        data["org_id"] = org_id
    resp = pd_post("/api/v1/notes", data)
    return resp["data"]["id"]


# ── Search (cross-entity) ────────────────────────────────────────────

def search_all(term: str, item_types: str = "deal,person,organization",
               limit: int = 20) -> list[dict]:
    resp = pd_get("/api/v2/itemSearch", {
        "term": term,
        "item_types": item_types,
        "limit": limit,
    })
    items = resp.get("data", {})
    if isinstance(items, dict):
        items = items.get("items", [])
    return items or []


# ── Sync helpers ──────────────────────────────────────────────────────

def sync_hash(fields: dict) -> str:
    raw = json.dumps(fields, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()


# ── LangChain Tools for agents ────────────────────────────────────────

class PipedriveSearchArgs(BaseModel):
    term: str = PydField(description="Search term (company name, person name, etc.)")


def _pd_search_tool(term: str) -> str:
    results = search_all(term)
    if not results:
        return "No results found in Pipedrive."
    formatted = []
    for r in results[:10]:
        item = r.get("item", r)
        formatted.append({
            "type": item.get("type", "unknown"),
            "id": item.get("id"),
            "title": item.get("title") or item.get("name", ""),
        })
    return json.dumps(formatted, default=str)


pipedrive_search = StructuredTool.from_function(
    func=_pd_search_tool,
    name="pipedrive_search",
    description="Search Pipedrive CRM for deals, persons, or organizations by name.",
    args_schema=PipedriveSearchArgs,
)


class CreateDealArgs(BaseModel):
    company_name: str = PydField(description="Company name for the deal title.")
    pipeline: str = PydField(default="deal_sourcing", description="deal_sourcing or lp_fundraising")
    stage_name: str = PydField(default="Sourced", description="Stage name within the pipeline.")
    value: Optional[float] = PydField(default=None, description="Deal value in EUR.")


def _pd_create_deal_tool(company_name: str, pipeline: str = "deal_sourcing",
                         stage_name: str = "Sourced",
                         value: float | None = None) -> str:
    pipelines = ensure_pipelines()
    pl = pipelines.get(pipeline)
    if not pl:
        return f"Unknown pipeline: {pipeline}"
    stage_id = pl["stages"].get(stage_name)
    if not stage_id:
        return f"Unknown stage: {stage_name}. Available: {list(pl['stages'].keys())}"
    deal_id = create_deal(
        title=company_name,
        pipeline_id=pl["pipeline_id"],
        stage_id=stage_id,
        value=value,
    )
    return json.dumps({"deal_id": deal_id, "pipeline": pipeline, "stage": stage_name})


pipedrive_create_deal = StructuredTool.from_function(
    func=_pd_create_deal_tool,
    name="pipedrive_create_deal",
    description="Create a new deal in Pipedrive (deal sourcing or LP fundraising pipeline).",
    args_schema=CreateDealArgs,
)


class LogActivityArgs(BaseModel):
    subject: str = PydField(description="Activity subject line.")
    activity_type: str = PydField(default="email", description="email | call | meeting | task")
    deal_id: Optional[int] = PydField(default=None, description="Pipedrive deal ID to link.")
    note: str = PydField(default="", description="Activity notes / email body.")
    due_date: Optional[str] = PydField(default=None, description="Due date (YYYY-MM-DD) for scheduled activities.")
    done: bool = PydField(default=False, description="Whether activity is already completed.")


def _pd_log_activity_tool(subject: str, activity_type: str = "email",
                          deal_id: int | None = None, note: str = "",
                          due_date: str | None = None,
                          done: bool = False) -> str:
    act_id = create_activity(
        subject=subject,
        activity_type=activity_type,
        deal_id=deal_id,
        note=note,
        due_date=due_date,
        done=done,
    )
    return json.dumps({"activity_id": act_id, "type": activity_type, "subject": subject})


pipedrive_log_activity = StructuredTool.from_function(
    func=_pd_log_activity_tool,
    name="pipedrive_log_activity",
    description="Log an activity (email, call, meeting, task) in Pipedrive, optionally linked to a deal.",
    args_schema=LogActivityArgs,
)


class UpdateDealStageArgs(BaseModel):
    deal_id: int = PydField(description="Pipedrive deal ID.")
    pipeline: str = PydField(default="deal_sourcing", description="deal_sourcing or lp_fundraising")
    stage_name: str = PydField(description="New stage name.")


def _pd_update_stage_tool(deal_id: int, pipeline: str = "deal_sourcing",
                          stage_name: str = "") -> str:
    pipelines = ensure_pipelines()
    pl = pipelines.get(pipeline)
    if not pl:
        return f"Unknown pipeline: {pipeline}"
    stage_id = pl["stages"].get(stage_name)
    if not stage_id:
        return f"Unknown stage: {stage_name}. Available: {list(pl['stages'].keys())}"
    update_deal(deal_id, stage_id=stage_id)
    return json.dumps({"deal_id": deal_id, "stage": stage_name, "updated": True})


pipedrive_update_stage = StructuredTool.from_function(
    func=_pd_update_stage_tool,
    name="pipedrive_update_stage",
    description="Move a Pipedrive deal to a different stage within its pipeline.",
    args_schema=UpdateDealStageArgs,
)
