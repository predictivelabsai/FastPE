from __future__ import annotations
from functools import lru_cache

from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.properties import search_properties, get_property
from tools.market import fetch_market_signals
from tools.rag import retrieve_documents
from tools.search import web_search
from tools.capital import crm_lookup
from tools.pipedrive import (
    pipedrive_search, pipedrive_create_deal,
    pipedrive_log_activity, pipedrive_update_stage,
)

SPEC = AGENTS_BY_SLUG["outreach_sequencer"]
TOOLS = [
    search_properties, get_property, fetch_market_signals,
    retrieve_documents, web_search, crm_lookup,
    pipedrive_search, pipedrive_create_deal,
    pipedrive_log_activity, pipedrive_update_stage,
]


@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
