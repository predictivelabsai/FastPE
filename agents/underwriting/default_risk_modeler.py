from functools import lru_cache
from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.credit import model_default_risk
from tools.financials import normalize_ltm
from tools.properties import get_company

SPEC = AGENTS_BY_SLUG["default_risk_modeler"]
TOOLS = [get_company, normalize_ltm, model_default_risk]

@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
