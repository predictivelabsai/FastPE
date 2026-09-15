"""Self-registering BYOK routes: the settings page and its save/remove actions.

Follows the suite convention of a vendored module that wires itself into a host
app given ``rt`` (à la ``account_auth.register_fasthtml_routes``). Pass a
``page_builder(session, *content)`` to nest the settings page in the product's
chrome; without one it renders a minimal standalone page.
"""
from __future__ import annotations

from fasthtml.common import A, Div, H2, Style, Title
from starlette.responses import RedirectResponse

from . import gate, store, ui

_STANDALONE_CSS = """
body{background:#f5f8f5;color:#1a2b1a;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;}
.byok-wrap{max-width:600px;margin:48px auto;padding:0 16px;}
.byok-wrap h2{font-size:20px;margin:0 0 4px;}
.byok-wrap .card{background:#fff;border:1px solid #d5dbd5;border-radius:10px;padding:16px 18px;margin-bottom:16px;}
.byok-wrap .btn{padding:7px 13px;border-radius:6px;border:1px solid #d5dbd5;background:#fff;
  cursor:pointer;font-size:13px;text-decoration:none;color:#1a2b1a;display:inline-block;}
.byok-wrap .btn.primary{background:#2f855a;color:#fff;border-color:#2f855a;}
.byok-wrap .btn.sm{padding:4px 9px;font-size:12px;}
.byok-wrap .back{font-size:13px;color:#2f855a;text-decoration:none;}
:root{--text-mute:#667;--border:#d5dbd5;--surface:#fff;--accent:#2f855a;}
"""


def _usage(org_id: str):
    rec = store.get_record(org_id)
    has = bool(rec and rec["api_key_enc"])
    prov = rec["provider"] if rec else None
    used = int(rec["free_used"]) if rec else 0
    return used, gate.FREE_LIMIT, has, prov


def register_routes(rt, config) -> None:
    get_org = config["get_org"]
    page_builder = config["page_builder"]
    app_name = config.get("app_name", "FastSME")

    def _render(session, *content):
        if page_builder:
            return page_builder(session, *content)
        return (
            Title(f"AI settings · {app_name}"),
            Style(_STANDALONE_CSS),
            Div(
                A("← Back to app", href="/", cls="back"),
                H2(f"{app_name} · AI settings"),
                *content,
                cls="byok-wrap",
            ),
        )

    @rt("/byok")
    def byok_settings(session, saved: int = 0):
        org = get_org(session)
        if not org:
            return RedirectResponse("/", status_code=303)
        used, lim, has, prov = _usage(str(org))
        return _render(session, ui.settings_card(used, lim, has, prov, saved=bool(saved)))

    @rt("/byok/save", methods=["POST"])
    def byok_save(session, provider: str = "xai", api_key: str = "", model: str = ""):
        org = get_org(session)
        if not org:
            return RedirectResponse("/", status_code=303)
        api_key = (api_key or "").strip()
        if api_key:
            store.set_key(str(org), (provider or "xai").strip().lower(), api_key,
                          (model or "").strip() or None)
        return RedirectResponse("/byok?saved=1", status_code=303)

    @rt("/byok/remove", methods=["POST"])
    def byok_remove(session):
        org = get_org(session)
        if org:
            store.clear_key(str(org))
        return RedirectResponse("/byok", status_code=303)
