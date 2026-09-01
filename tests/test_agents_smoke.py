"""Light smoke tests.

These do NOT hit the LLM — they verify that every agent module builds, that
the router dispatches sensibly, and that key tools return real data against
the synthetic corpus.

Run with:  pytest -q tests
"""

from __future__ import annotations

import json

import pytest

from agents.base import cached_agent
from agents.registry import AGENTS, AGENTS_BY_SLUG
from agents import router as agent_router


@pytest.mark.parametrize("spec", AGENTS, ids=lambda s: s.slug)
def test_every_agent_builds(spec):
    graph = cached_agent(spec.slug)
    assert graph is not None


@pytest.mark.parametrize("message,expected_slug", [
    ("triage: DR VET veterinary clinic, €3.8M revenue", "deal_triage"),
    ("lbo: build a 5-year model", "pro_forma_builder"),
    ("ltm: normalize DR VET financials", "t12_normalizer"),
    ("memo: IC memo for Kardiolita", "investor_memo"),
    ("abstract: change-of-control terms across MSAs", "lease_abstractor"),
    ("vc: rank initiatives for DR VET", "capex_prioritizer"),
    ("ebitda: what's driving variance?", "opex_variance"),
    ("churn: which customers are at risk?", "tenant_churn"),
    ("price: where is pricing below market?", "rent_optimization"),
    ("scan: healthcare clinics in Lithuania", "market_scanner"),
    ("comps: healthcare clinics precedent M&A", "comp_finder"),
])
def test_prefix_routing(message, expected_slug):
    assert agent_router.route(message) == expected_slug


def test_free_form_routing_falls_back_sensibly():
    slug = agent_router.route("what's the EV/EBITDA multiple in SaaS right now?")
    assert slug in AGENTS_BY_SLUG


def test_company_search_returns_data():
    from tools.properties import search_companies
    out = json.loads(search_companies.invoke({"sector": "healthcare", "limit": 5}))
    assert out["count"] >= 1
    assert out["companies"][0]["sector"] == "healthcare"


def test_rag_retrieval_returns_citations():
    from rag.retriever import retrieve
    chunks = retrieve("change of control customer msa", k=3, doc_types=["msa"])
    assert len(chunks) >= 1
    assert all(c.doc_type == "msa" for c in chunks)


def test_normalize_ltm_emits_artifact():
    from tools.financials import normalize_ltm
    out = normalize_ltm.invoke({"slug_or_id": "1"})
    assert out.startswith("__ARTIFACT__")
    payload = json.loads(out[len("__ARTIFACT__"):])
    assert payload["kind"] == "table"
    assert payload["summary"]["ltm_revenue"] is not None


def test_lbo_round_trip():
    from tools.financials import build_lbo_model, compute_returns
    out = build_lbo_model.invoke({"slug_or_id": "2", "hold_years": 3})
    assert out.startswith("__ARTIFACT__")
    ret = json.loads(compute_returns.invoke({"slug_or_id": "2"}))
    assert "returns" in ret


def test_zero_argument_tool_has_concrete_schema():
    """LangChain must be able to expose no-argument tools to the model."""
    from tools.capital import portfolio_snapshot

    assert portfolio_snapshot.tool_call_schema.model_json_schema()["properties"] == {}
