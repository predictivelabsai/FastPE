from functools import lru_cache
from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.credit import monitor_credit_portfolio, test_covenant_headroom

SPEC = AGENTS_BY_SLUG["credit_portfolio_monitor"]
TOOLS = [monitor_credit_portfolio, test_covenant_headroom]

@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
