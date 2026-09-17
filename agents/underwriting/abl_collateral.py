from functools import lru_cache
from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.credit import calculate_borrowing_base

SPEC = AGENTS_BY_SLUG["abl_collateral"]
TOOLS = [calculate_borrowing_base]

@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
