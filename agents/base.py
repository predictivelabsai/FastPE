"""Shared helpers for building LangGraph ReAct agents.

Every agent module exports `build()` that returns a cached graph. This module
provides the canonical factory so agents stay consistent in shape.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from agents.registry import AgentSpec
from utils.llm import build_agent_llm

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "system"
SHARED_PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "shared" / "pe_context.md"


def _load_system_prompt(slug: str) -> str:
    shared = SHARED_PROMPT_FILE.read_text() if SHARED_PROMPT_FILE.exists() else ""
    specific_file = PROMPTS_DIR / f"{slug}.md"
    specific = specific_file.read_text() if specific_file.exists() else ""
    if not specific:
        log.warning("no system prompt for %s — using shared context only", slug)
    return (shared + "\n\n" + specific).strip()


def build_agent(spec: AgentSpec, tools: list[BaseTool], model=None):
    """Build a LangGraph ReAct agent with Grok + the provided tools.

    Intentionally NOT cached here — caller may want different tool sets per
    session. Agent module-level `build()` functions own their own caching.

    When ``model`` is provided (e.g. a per-request BYOK chat model), it is used
    instead of the default house LLM. Otherwise the standard cached house model
    (``build_agent_llm``) is used, preserving existing behaviour exactly.
    """
    system = _load_system_prompt(spec.slug)
    llm = model or build_agent_llm()
    return create_react_agent(llm, tools, prompt=system or None)


@lru_cache(maxsize=64)
def _cached_agent(slug: str):
    """Fetch a cached agent by slug. Looks up the module and calls its build()."""
    from agents import registry
    spec = registry.by_slug(slug)
    if spec is None:
        raise ValueError(f"unknown agent slug: {slug}")

    # Convention: agents/<category>/<slug>.py exports build()
    import importlib
    module = importlib.import_module(f"agents.{spec.category}.{spec.slug}")
    return module.build()


def cached_agent(slug: str, model=None):
    """Return an agent graph for ``slug``.

    Default (``model=None``): the cached house agent — identical to before.
    With ``model`` set (per-request BYOK model): build a FRESH agent bound to
    that model, bypassing the lru_cache so the house singleton stays untouched.
    """
    if model is None:
        return _cached_agent(slug)

    from agents import registry
    spec = registry.by_slug(slug)
    if spec is None:
        raise ValueError(f"unknown agent slug: {slug}")
    import importlib
    module = importlib.import_module(f"agents.{spec.category}.{spec.slug}")
    return build_agent(spec, module.TOOLS, model=model)
