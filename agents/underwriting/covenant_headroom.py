from functools import lru_cache
from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.credit import test_covenant_headroom
from tools.financials import normalize_ltm

SPEC = AGENTS_BY_SLUG["covenant_headroom"]
TOOLS = [normalize_ltm, test_covenant_headroom]

@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
