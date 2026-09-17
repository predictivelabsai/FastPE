from functools import lru_cache
from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.credit import construct_credit_portfolio

SPEC = AGENTS_BY_SLUG["credit_portfolio_constructor"]
TOOLS = [construct_credit_portfolio]

@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
