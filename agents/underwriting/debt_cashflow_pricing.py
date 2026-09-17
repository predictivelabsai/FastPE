from functools import lru_cache
from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.credit import model_debt_cashflows
from tools.financials import normalize_ltm

SPEC = AGENTS_BY_SLUG["debt_cashflow_pricing"]
TOOLS = [normalize_ltm, model_debt_cashflows]

@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
