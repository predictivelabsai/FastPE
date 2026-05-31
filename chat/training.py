"""Training page — PE Hero game UI.

/app/training → game chat interface
"""

from __future__ import annotations

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Div, Span, Button, Form, Input,
)

from app import rt
from chat.components import left_pane, signin_overlay, copilot_pane, copilot_toggle_btn
from chat.layout import _versioned, common_scripts
from utils.session import get_currency
from utils.i18n import t, get_lang
from chat.routes import _ensure_user, _list_sessions
from landing.components import TAILWIND_CONFIG, _favicon_links
from game.routes import register_game_routes

register_game_routes(rt)


def _head():
    return Head(
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Title("PE Hero Training · PEHero"),
        *_favicon_links(),
        Link(rel="preconnect", href="https://fonts.googleapis.com"),
        Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
        Link(rel="stylesheet",
             href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"),
        *common_scripts(),
        Script(src="https://cdn.tailwindcss.com"),
        Script(NotStr(TAILWIND_CONFIG)),
        Link(rel="stylesheet", href="/static/site.css"),
        Link(rel="stylesheet", href=_versioned("app.css")),
        Link(rel="stylesheet", href="/static/pipeline.css"),
    )


@rt("/app/training")
def training_page(sess):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)

    body = Body(
        signin_overlay(lang=lang),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="",
                  current_currency=get_currency(sess),
                  current_path="/app/training", lang=lang),
        Div(
            Div(
                Div(
                    Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    Span("PE Hero Training", cls="chat-header-title"),
                    cls="chat-header-left",
                ),
                Div(
                    Button("Reset Game", cls="integration-action-btn danger",
                           style="font-size:.7rem; padding:.25rem .6rem;",
                           onclick="fetch('/app/training/reset',{method:'POST'}).then(()=>location.reload())"),
                    copilot_toggle_btn(lang=lang),
                    cls="chat-header-actions",
                ),
                cls="chat-header",
            ),
            Div(
                Div(id="messages", cls="messages",
                    style="flex:1; overflow-y:auto; padding:1rem;"),
                Div(
                    Form(
                        Input(type="text", id="training-input",
                              placeholder="Type your choice or action...",
                              cls="chat-input", style="flex:1;",
                              autocomplete="off"),
                        Button("Send", type="submit", cls="send-btn"),
                        id="training-form",
                        cls="chat-form",
                        style="display:flex; gap:.5rem; padding:.5rem;",
                    ),
                    cls="chat-input-wrap",
                ),
                cls="chat-body",
                style="display:flex; flex-direction:column; height:calc(100vh - 48px);",
            ),
            cls="center-pane pipeline-center",
            style="overflow:hidden;",
        ),
        copilot_pane(
            page_name="Training",
            page_context={"page": "PE Hero Training Game"},
            lang=lang,
        ),
        Script(src=_versioned("chat.js")),
        Script(src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"),
        Script(src=_versioned("copilot.js")),
        Script(src=_versioned("training.js")),
        cls="bg-bg text-ink font-sans antialiased app",
    )
    return Html(_head(), body, lang=lang)
