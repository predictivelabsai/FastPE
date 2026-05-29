"""Full 3-pane chat page layout."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Div, Span,
)

from landing.components import SITE_NAME, TAILWIND_CONFIG, _favicon_links
from chat.components import left_pane, center_pane, right_pane, signin_overlay

_STATIC = Path(__file__).resolve().parent.parent / "static"


def _versioned(filename: str) -> str:
    p = _STATIC / filename
    h = hashlib.md5(p.read_bytes()).hexdigest()[:8] if p.exists() else "0"
    return f"/static/{filename}?v={h}"


def chat_page(*, user_email: str | None, sessions: list, current_sid: str = "",
              messages: list, current_agent_slug: str | None = None,
              current_currency: str = "EUR", readonly: bool = False,
              lang: str = "en"):
    head = Head(
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Meta(name="description", content="PEHero — agentic AI for private equity deal teams"),
        Title(f"App · {SITE_NAME}"),
        *_favicon_links(),
        Link(rel="preconnect", href="https://fonts.googleapis.com"),
        Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
        Link(
            rel="stylesheet",
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap",
        ),
        Script(src="https://cdn.tailwindcss.com"),
        Script(NotStr(TAILWIND_CONFIG)),
        Script(src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"),
        Link(rel="stylesheet", href="/static/site.css"),
        Link(rel="stylesheet", href=_versioned("app.css")),
    )
    body = Body(
        signin_overlay(lang=lang),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=user_email, sessions=sessions, current_sid=current_sid,
                  current_currency=current_currency, lang=lang),
        center_pane(messages=messages, current_agent_slug=current_agent_slug, readonly=readonly, lang=lang),
        right_pane(lang=lang),
        Script(src=_versioned("chat.js")),
        cls="bg-bg text-ink font-sans antialiased app",
    )
    return Html(head, body, lang=lang)
