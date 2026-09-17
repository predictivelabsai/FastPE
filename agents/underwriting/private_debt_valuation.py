from functools import lru_cache
from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.credit import value_private_debt, model_debt_cashflows

SPEC = AGENTS_BY_SLUG["private_debt_valuation"]
TOOLS = [model_debt_cashflows, value_private_debt]

@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
