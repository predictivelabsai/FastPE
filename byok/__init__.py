"""BYOK — a drop-in "bring your own API key" module for the FastSME suite.

One vendored package, copied into each product, providing:

  - a per-organization free-query gate (lifetime limit on the deployment key),
  - encrypted per-organization storage of the org's own LLM API key,
  - a LangChain chat-model factory (xAI / OpenAI / Anthropic / Google) used for
    both the house key and BYOK keys, and
  - self-registering ``/byok`` settings routes + reusable UI fragments.

Wiring in a host app (typically two lines in the entrypoint)::

    import byok
    byok.register(rt, app, get_org=my_org_resolver, app_name="FastCRM",
                  page_builder=lambda s, *c: page("ai", ENV, user(s), thread(s), *c))

Then, at the AI entrypoint::

    gate = byok.begin_query(session)
    if gate.blocked:
        ...  # show gate.gate_markdown
    else:
        async for chunk in gate.llm.astream([...]):
            ...
        gate.commit()

The public surface is intentionally small: ``register``, ``begin_query``,
``usage``, ``usage_banner``, ``org_for``.
"""
from __future__ import annotations

from . import gate as _gate
from . import llm, store, ui
from . import routes as _routes

__all__ = ["register", "begin_query", "usage", "usage_banner", "org_for",
           "default_get_org", "llm", "store"]

_CONFIG: dict = {"get_org": None, "app_name": "FastSME", "page_builder": None}


def default_get_org(session):
    """Best-effort org resolver tolerant of every session shape in the suite.

    Prefers the SSO ``suite_identity.org_id``; falls back to the logged-in user
    (email string, a user dict's org/email/id, or a ``user_id``). Returns None
    when there's no identity at all.
    """
    if not session:
        return None
    ident = session.get("suite_identity") or {}
    org = ident.get("org_id") or ident.get("org_name")
    if org:
        return org
    u = session.get("user")
    if isinstance(u, dict):
        return u.get("organization_id") or u.get("org_id") or u.get("email") or u.get("id")
    if u:
        return u
    return session.get("user_id")


def register(rt, app=None, *, get_org=None, app_name="FastSME", page_builder=None):
    """Initialize the store and register the ``/byok`` routes on ``rt``."""
    _CONFIG["get_org"] = get_org or default_get_org
    _CONFIG["app_name"] = app_name
    _CONFIG["page_builder"] = page_builder
    store.init()
    _routes.register_routes(rt, _CONFIG)
    return _CONFIG


def _get_org():
    return _CONFIG["get_org"] or default_get_org


def begin_query(session):
    """Authorize + route one AI request. See :class:`byok.gate.QueryGate`."""
    return _gate.begin_query(session, _get_org())


def org_for(session):
    return _get_org()(session)


def usage(session):
    """Return ``(used, limit, has_key, provider)`` for banners/badges."""
    org = org_for(session)
    if not org:
        return (0, _gate.FREE_LIMIT, False, None)
    rec = store.get_record(str(org))
    has = bool(rec and rec["api_key_enc"])
    prov = rec["provider"] if rec else None
    used = int(rec["free_used"]) if rec else 0
    return (used, _gate.FREE_LIMIT, has, prov)


def usage_banner(session):
    """A low-quota nudge component, or None when nothing needs saying."""
    return ui.usage_banner(*usage(session))
