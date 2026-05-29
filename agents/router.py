"""Intent router — maps a user message to an agent slug.

Order of preference:
  1. Explicit prefix (`triage:`, `memo:`, etc.) — from AgentSpec.prefix
  2. Keyword heuristics per agent category
  3. LLM fallback classifier (cheap Grok call)
"""

from __future__ import annotations

import logging
import re

from agents.registry import AGENTS, AGENTS_BY_SLUG
from utils.llm import build_llm

log = logging.getLogger(__name__)


# ── Language-intent pre-filter ─────────────────────────────────────────
_LANG_NAMES = r"(?:lithuanian|english|estonian|finnish|swedish|lietuviškai|angliškai|lietuvių|anglų|eesti|soome|rootsi|suomeksi|ruotsiksi|finska|svenska)"
_LANG_INTENT_RE = re.compile(
    rf"\b(?:write|respond|reply|translate|switch|change|speak|answer|draft)\b.*\b(?:in|to|into)\s+{_LANG_NAMES}\b",
    re.IGNORECASE,
)
_LANG_ONLY_RE = re.compile(
    rf"^(?:can you |please |could you )?(?:write|respond|reply|translate|switch|change|speak|answer|draft)"
    rf".*\b(?:in|to|into)\s+{_LANG_NAMES}\b[?.!]?\s*$",
    re.IGNORECASE,
)


def is_language_intent(message: str) -> bool:
    """Return True if the message is primarily about switching language."""
    return bool(_LANG_ONLY_RE.search(message))


# Keyword hints per category. Tuned to be specific enough to avoid false
# positives on generic terms like "deal" or "revenue".
CATEGORY_HINTS: dict[str, list[str]] = {
    "sourcing": [
        "find deals", "surface", "off market", "off-market", "on market",
        "precedent", "trading comps", "transaction comps", "triage",
        "go no-go", "go/no-go", "scan the market", "seller intent",
        "likely to sell", "founder", "proprietary deal",
        "outreach email", "cold email", "intro email", "broker email",
        "loi", "letter of intent", "ioi", "indication of interest",
    ],
    "underwriting": [
        "cap table", "ltm", "trailing twelve months", "qoe",
        "quality of earnings", "lbo", "lbo model",
        "5-year", "sensitivity", "irr", "moic", "dscr",
        "leverage", "unitranche", "mezz", "mezzanine", "debt stack",
        "ev/ebitda", "ev-ebitda", "entry multiple", "exit multiple",
    ],
    "diligence": [
        "data room", "vdr", "due diligence", "diligence",
        "abstract", "contract abstract", "msa", "customer contract",
        "legal", "regulatory", "licensure", "litigation",
        "operational diligence", "100-day plan", "ops review",
        "esg", "environmental", "governance",
    ],
    "capital": [
        "ic memo", "investment memo", "memo", "teaser", "lp letter",
        "lp update", "investor update", "limited partner", "crm",
        "prospect", "fundraising", "gp", "general partner",
    ],
    "asset_mgmt": [
        "pricing", "price increase", "renewal pricing",
        "ebitda variance", "budget variance", "over budget",
        "value creation", "value-creation", "100-day", "portco",
        "portfolio company", "customer churn", "renewal likelihood",
        "retention",
    ],
}


_PREFIX_MAP: dict[str, str] = {a.prefix.lower(): a.slug for a in AGENTS}


def _prefix_match(message: str) -> str | None:
    lower = message.lower().strip()
    for prefix, slug in _PREFIX_MAP.items():
        if lower.startswith(prefix):
            return slug
    return None


def _keyword_scores(message: str) -> dict[str, int]:
    lower = message.lower()
    scores: dict[str, int] = {}
    for agent in AGENTS:
        # Prioritize agent-name presence
        if agent.name.lower() in lower:
            scores[agent.slug] = scores.get(agent.slug, 0) + 5
        # Category-level hints
        hints = CATEGORY_HINTS.get(agent.category, [])
        for h in hints:
            if h in lower:
                scores[agent.slug] = scores.get(agent.slug, 0) + (2 if " " in h else 1)
    return scores


def _best_in_category_for(message: str) -> str | None:
    """When the message looks like a category, pick a good default agent for it."""
    lower = message.lower()
    if "triage" in lower or "go/no-go" in lower or "screen" in lower:
        return "deal_triage"
    if "lbo" in lower or "pro forma" in lower or "proforma" in lower:
        return "pro_forma_builder"
    if "ic memo" in lower or "memo" in lower:
        return "investor_memo"
    if "outreach" in lower or "cold email" in lower or "intro email" in lower or "broker email" in lower:
        return "outreach_email"
    if "loi" in lower or "letter of intent" in lower or "ioi" in lower or "indication of interest" in lower:
        return "loi_writer"
    if "precedent" in lower or "transaction comps" in lower or "trading comps" in lower:
        return "comp_finder"
    if "cap table" in lower:
        return "rent_roll_parser"
    if "ltm" in lower or "quality of earnings" in lower or "qoe" in lower:
        return "t12_normalizer"
    if "msa" in lower or "contract abstract" in lower:
        return "lease_abstractor"
    if "value creation" in lower or "100-day" in lower or "100 day" in lower:
        return "capex_prioritizer"
    if "ebitda variance" in lower or "budget variance" in lower:
        return "opex_variance"
    return None


_LLM_CLASSIFIER_PROMPT = """You are a router for a private-equity deal platform. Return the SLUG of the best specialist agent for the user's message. Pick from this list only, output just the slug with no extra text:

{agent_list}

User message: {message}

Best slug:"""


def _llm_classify(message: str) -> str:
    try:
        agent_list = "\n".join(f"- {a.slug}: {a.one_liner}" for a in AGENTS)
        prompt = _LLM_CLASSIFIER_PROMPT.format(agent_list=agent_list, message=message[:500])
        resp = build_llm().invoke(prompt).content.strip().split()[0].strip(":.,")
        if resp in AGENTS_BY_SLUG:
            return resp
    except Exception as e:  # noqa: BLE001
        log.warning("llm classifier failed: %s", e)
    return "deal_triage"  # sane default


def route(message: str, forced_slug: str | None = None) -> str:
    """Return the best agent slug for `message`."""
    if forced_slug and forced_slug in AGENTS_BY_SLUG:
        return forced_slug

    slug = _prefix_match(message)
    if slug:
        return slug

    slug = _best_in_category_for(message)
    if slug:
        return slug

    scores = _keyword_scores(message)
    if scores:
        return max(scores, key=scores.get)

    return _llm_classify(message)


def strip_prefix(message: str) -> str:
    """Remove the leading `xxx:` prefix from a message, if present."""
    m = re.match(r"^\s*(\w{2,10}):\s*", message)
    if m and m.group(1).lower() + ":" in _PREFIX_MAP:
        return message[m.end():]
    return message
