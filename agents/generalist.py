"""Generalist fallback agent — used for prompts that don't match a specialist,
and as the safety net while Phase 6 agents are being built out.

Has access to the company search + RAG retrieval tools, so it can answer most
PE questions meaningfully even without a specialist routing.
"""

from __future__ import annotations

from functools import lru_cache

from agents.registry import AgentSpec
from agents.base import build_agent
from tools.properties import search_properties, get_property
from tools.rag import retrieve_documents


SPEC = AgentSpec(
    slug="generalist",
    name="Generalist",
    category="sourcing",  # nominal; not shown in UI
    icon="◆",
    one_liner="Falls back when no specialist matches.",
    description="Catch-all agent with access to the property catalog and the RAG index.",
    prefix="ask:",
    example_prompts=(),
)

SYSTEM_PROMPT = """You are PEHero, an AI assistant for private-equity and private-credit teams and portfolio operations. You have access to:
- A company catalog (synthetic portfolio-company + pipeline targets across software, healthcare, industrials, consumer, business services, financial services)
- A RAG index of CIMs, QoE reports, MSAs, legal DD, ESG reports, tax memos, tech DDQs, and industry reports

When answering, favor tool calls over guessing. When you cite documents, always name the document title.
Be concise. Use markdown bullets for lists. Use **bold** for key figures.
"""


TOOLS = [search_properties, get_property, retrieve_documents]


@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
