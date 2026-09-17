from functools import lru_cache
from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.credit import model_recovery_waterfall
from tools.properties import get_company

SPEC = AGENTS_BY_SLUG["recovery_waterfall"]
TOOLS = [get_company, model_recovery_waterfall]

@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
