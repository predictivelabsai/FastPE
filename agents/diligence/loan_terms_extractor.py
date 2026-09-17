from functools import lru_cache
from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.diligence import abstract_contracts, list_documents

SPEC = AGENTS_BY_SLUG["loan_terms_extractor"]
TOOLS = [abstract_contracts, list_documents]

@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
