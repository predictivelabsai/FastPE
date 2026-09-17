from functools import lru_cache
from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.capital import deal_brief
from tools.credit import model_default_risk, test_covenant_headroom, model_recovery_waterfall

SPEC = AGENTS_BY_SLUG["credit_memo_writer"]
TOOLS = [deal_brief, model_default_risk, test_covenant_headroom, model_recovery_waterfall]

@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
