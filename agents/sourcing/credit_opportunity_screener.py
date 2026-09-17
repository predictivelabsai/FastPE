from functools import lru_cache
from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.credit import screen_credit_opportunity
from tools.properties import get_company, search_companies

SPEC = AGENTS_BY_SLUG["credit_opportunity_screener"]
TOOLS = [search_companies, get_company, screen_credit_opportunity]

@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
