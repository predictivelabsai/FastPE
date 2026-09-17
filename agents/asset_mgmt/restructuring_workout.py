from functools import lru_cache
from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.credit import compare_workout_options, model_recovery_waterfall

SPEC = AGENTS_BY_SLUG["restructuring_workout"]
TOOLS = [model_recovery_waterfall, compare_workout_options]

@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
