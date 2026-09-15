"""The query gate: how a single AI request is authorized and routed.

Policy (per organization, keyed by whatever ``get_org(session)`` returns):

  1. Org has a stored BYOK key  -> allowed, unlimited, routed through their key.
  2. No key, under the free limit -> allowed on the house key; caller commits the
     count on success.
  3. No key, at the free limit    -> blocked; caller shows ``gate_markdown``.
  4. No key and the deployment has no house key -> blocked with a setup hint.

The free limit is lifetime (``$BYOK_FREE_QUERY_LIMIT``, default 5).
"""
from __future__ import annotations

import logging
import os

from . import llm as _llm
from . import store

log = logging.getLogger("byok")

FREE_LIMIT = int(os.getenv("BYOK_FREE_QUERY_LIMIT", "5"))


class QueryGate:
    """Outcome of :func:`begin_query` for one AI request."""

    def __init__(self, org_id, blocked, reason, model=None, provider=None, used=0):
        self.org_id = org_id
        self.blocked = blocked
        self.reason = reason        # 'byok' | 'free' | 'limit' | 'no_house_key' | 'no_identity'
        self.llm = model            # LangChain BaseChatModel (None when blocked)
        self.provider = provider
        self.used = used
        self.limit = FREE_LIMIT

    @property
    def used_byok(self) -> bool:
        return self.reason == "byok"

    @property
    def gate_markdown(self) -> str:
        if self.reason == "limit":
            return (
                f"You've used all **{self.limit} free AI queries** for this workspace. "
                "To keep using the assistant, add your organization's own API key "
                "(xAI, OpenAI, Anthropic or Google) on the "
                "**[BYOK settings page](/byok)** — it's encrypted and stays private "
                "to your workspace."
            )
        if self.reason == "no_house_key":
            return (
                "Free-form AI chat isn't configured on this deployment yet. "
                "Add your organization's own API key on the "
                "**[BYOK settings page](/byok)** to enable it."
            )
        if self.reason == "no_identity":
            return "Please sign in to use the AI assistant."
        return ""

    def commit(self) -> None:
        """Record one free-tier query. No-op for BYOK or blocked requests."""
        if self.reason == "free" and self.org_id:
            store.increment_free(self.org_id)


def begin_query(session, get_org) -> QueryGate:
    org = get_org(session) if session is not None else None
    if not org:
        return QueryGate(None, True, "no_identity")
    org_id = str(org)

    # 1. BYOK key present -> unlimited, use their key.
    key = store.get_key(org_id)
    if key:
        provider, api_key, model = key
        try:
            m = _llm.build_chat_model(provider, api_key, model)
        except Exception as e:  # bad key config -> surface as a blocked gate
            log.warning("BYOK model build failed for org %s: %s", org_id, e)
            return QueryGate(org_id, True, "no_house_key")
        return QueryGate(org_id, False, "byok", model=m, provider=provider)

    # 2/3. Free tier on the house key.
    used = store.free_used(org_id)
    if used >= FREE_LIMIT:
        return QueryGate(org_id, True, "limit", used=used)

    provider = _llm.house_provider()
    hk = _llm.house_key(provider)
    if not hk:
        return QueryGate(org_id, True, "no_house_key", used=used)
    m = _llm.build_chat_model(provider, hk, _llm.house_model(provider))
    return QueryGate(org_id, False, "free", model=m, provider=provider, used=used)
