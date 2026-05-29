"""Web search tool — Tavily default, EXA fallback.

Used by sourcing agents when they need to pull info that isn't in the PE OLTP
corpus (e.g. "what happened to the Kardiolita deal last year?",
"find recent M&A activity in Baltic healthcare").

Hides the provider behind a single StructuredTool. If neither key is set the
tool returns a neutral "search unavailable" string so agents can degrade
gracefully rather than crash.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from utils.config import settings

log = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"
EXA_URL = "https://api.exa.ai/search"


class SearchArgs(BaseModel):
    query: str = Field(description="Natural-language web search query.")
    max_results: int = Field(default=6, ge=1, le=15)
    days: Optional[int] = Field(default=None, description="Recency window in days (optional).")


def _tavily(query: str, max_results: int, days: int | None) -> dict | None:
    key = settings().tavily_api_key
    if not key:
        return None
    payload = {
        "api_key": key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": True,
    }
    if days:
        payload["days"] = days
    try:
        r = httpx.post(TAVILY_URL, json=payload, timeout=20.0)
        r.raise_for_status()
        data = r.json()
        return {
            "provider": "tavily",
            "answer": data.get("answer"),
            "results": [
                {"title": h.get("title"), "url": h.get("url"),
                 "snippet": h.get("content"), "score": h.get("score")}
                for h in (data.get("results") or [])
            ],
        }
    except Exception as e:  # noqa: BLE001
        log.warning("tavily failed: %s", e)
        return None


def _exa(query: str, max_results: int, days: int | None) -> dict | None:
    key = settings().exa_api_key
    if not key:
        return None
    payload = {
        "query": query,
        "numResults": max_results,
        "type": "auto",
        "contents": {"text": {"maxCharacters": 800}, "highlights": {"numSentences": 3}},
    }
    if days:
        from datetime import datetime, timedelta
        payload["startPublishedDate"] = (datetime.utcnow() - timedelta(days=days)).isoformat()
    headers = {"x-api-key": key, "content-type": "application/json"}
    try:
        r = httpx.post(EXA_URL, json=payload, headers=headers, timeout=20.0)
        r.raise_for_status()
        data = r.json()
        return {
            "provider": "exa",
            "answer": None,
            "results": [
                {"title": h.get("title"), "url": h.get("url"),
                 "snippet": (h.get("text") or "")[:800],
                 "score": h.get("score")}
                for h in (data.get("results") or [])
            ],
        }
    except Exception as e:  # noqa: BLE001
        log.warning("exa failed: %s", e)
        return None


def _web_search(**kw) -> str:
    args = SearchArgs(**kw)
    data = _tavily(args.query, args.max_results, args.days)
    if not data:
        data = _exa(args.query, args.max_results, args.days)
    if not data:
        return "Search unavailable — no TAVILY_API_KEY / EXA_API_KEY configured, or both providers failed."

    items = data["results"]
    subtitle = f"{data['provider']} · {len(items)} results"
    if data.get("answer"):
        subtitle += " · AI summary included"

    artifact = {
        "kind": "citations",
        "title": f"Web search: {args.query[:70]}",
        "subtitle": subtitle,
        "items": items,
    }
    return "__ARTIFACT__" + json.dumps(artifact)


web_search = StructuredTool.from_function(
    func=_web_search,
    name="web_search",
    description=("Search the public web for news, press releases, filings, or anything "
                 "outside the PEHero PE corpus. Returns title + URL + snippet. "
                 "Tavily is preferred; EXA is fallback."),
    args_schema=SearchArgs,
)
