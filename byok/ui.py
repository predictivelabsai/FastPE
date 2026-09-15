"""FastHTML UI fragments for BYOK: the settings card and the usage banner.

These reuse the host app's ``.card`` / ``.btn`` classes so they inherit each
product's chrome, with a little scoped CSS for the BYOK-specific bits.
"""
from __future__ import annotations

from fasthtml.common import (
    A, Button, Div, Form, H3, Input, Label, Option, P, Select, Span, Style,
)

from . import llm

BYOK_CSS = """
.byok-card{max-width:560px;}
.byok-card label{display:block;font-size:12px;font-weight:600;margin:12px 0 4px;color:var(--text-mute,#667);}
.byok-card input,.byok-card select{width:100%;padding:8px 10px;border:1px solid var(--border,#d5dbd5);
  border-radius:6px;background:var(--surface,#fff);font-size:14px;box-sizing:border-box;}
.byok-card form{margin:0;}
.byok-card .row-actions{display:flex;gap:8px;align-items:center;margin-top:14px;flex-wrap:wrap;}
.byok-status{margin:6px 0 2px;font-size:13px;}
.byok-status .ok{color:#1a7f37;font-weight:600;}
.byok-status .warn{color:#b25a00;font-weight:600;}
.byok-banner{display:flex;gap:10px;align-items:center;font-size:13px;}
.byok-banner .btn{margin-left:auto;}
.byok-ok{color:#1a7f37;font-weight:600;}
"""


def settings_card(used: int, limit: int, has_key: bool, provider: str | None,
                  saved: bool = False):
    remaining = max(0, limit - used)
    opts = [
        Option(spec["label"], value=pid, selected=(pid == (provider or "xai")))
        for pid, spec in llm.PROVIDERS.items()
    ]

    if has_key:
        status = Div(
            Span(f"Active key: {llm.PROVIDERS.get(provider, {}).get('label', provider)}",
                 cls="ok"),
            cls="byok-status",
        )
    else:
        status = Div(
            Span(f"{used}/{limit} free queries used · {remaining} left",
                 cls=("warn" if remaining <= 1 else "")),
            cls="byok-status",
        )

    save_form = Form(
        Label("Provider"),
        Select(*opts, name="provider"),
        Label("API key"),
        Input(name="api_key", type="password", placeholder="xai-… / sk-… ",
              autocomplete="off"),
        Label("Model (optional)"),
        Input(name="model", placeholder="leave blank for the provider default"),
        Div(
            Button("Save key", cls="btn primary", type="submit"),
            (Span("✓ Saved", cls="byok-ok") if saved else None),
            cls="row-actions",
        ),
        method="post", action="/byok/save",
    )

    children = [
        Style(BYOK_CSS),
        Div(H3("Bring your own API key"), cls="card-header"),
        P("Add your organization's own LLM API key to unlock unlimited AI. "
          "Your key is encrypted at rest and used only within your workspace. "
          "New workspaces get a few free queries on the shared key first."),
        status,
        save_form,
    ]
    if has_key:
        children.append(
            Form(Button("Remove key", cls="btn"),
                 method="post", action="/byok/remove")
        )
    return Div(*children, cls="card byok-card")


def usage_banner(used: int, limit: int, has_key: bool, provider: str | None):
    """A small nudge shown near the assistant once free queries run low.

    Returns None when there's nothing to nag about (key present, or plenty left).
    """
    if has_key:
        return None
    remaining = max(0, limit - used)
    if remaining > 2:
        # Gentle post-login nudge while free queries are still plentiful.
        msg = "Tip: add your organization's own API key for unlimited AI. "
    elif remaining > 0:
        msg = (f"You have {remaining} free AI "
               f"{'query' if remaining == 1 else 'queries'} left. "
               "Add your own API key for unlimited access. ")
    else:
        msg = "You've used all your free AI queries. Add your own API key to continue. "
    return Div(
        Style(BYOK_CSS),
        Span("⚡"),
        Span(msg),
        A("Add API key", href="/byok", cls="btn sm primary"),
        cls="card byok-banner",
    )
