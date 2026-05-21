"""Instructions page — edit + save per-agent system prompts.

/app/instructions              → list all agents
/app/instructions/<slug>       → WYSIWYG editor (default) + markdown toggle + version history
POST /app/instructions/<slug>  → persist to file + pehero.prompt_versions

API:
GET  /app/api/prompt-versions/<slug>       → version list
GET  /app/api/prompt-version/<id>          → single version content
POST /app/api/prompt-versions/<slug>/revert → revert to version
"""

from __future__ import annotations

from pathlib import Path

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Div, Span, H1, H2, H3, H4, P, Ul, Li, A, Button,
    Form, Textarea, Input, Label,
)
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from app import rt
from agents.registry import AGENTS, AGENTS_BY_SLUG
from chat.components import left_pane, signin_overlay
from chat.layout import _versioned
from db.prompts import (
    save_prompt_version, count_prompt_versions,
    get_prompt_versions, get_prompt_version,
)
from utils.session import get_currency, currency_symbol
from chat.routes import _ensure_user, _list_sessions
from landing.components import TAILWIND_CONFIG, _favicon_links

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "system"
SHARED_DIR = Path(__file__).resolve().parent.parent / "prompts" / "shared"


def _head(title: str) -> Head:
    return Head(
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Title(f"{title} · PEHero"),
        *_favicon_links(),
        Link(rel="preconnect", href="https://fonts.googleapis.com"),
        Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
        Link(rel="stylesheet",
             href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"),
        Script(src="https://cdn.tailwindcss.com"),
        Script(NotStr(TAILWIND_CONFIG)),
        Link(rel="stylesheet", href="/static/site.css"),
        Link(rel="stylesheet", href=_versioned("app.css")),
        Link(rel="stylesheet", href="/static/pipeline.css"),
    )


def _editor_head(title: str) -> Head:
    """Head with Quill + marked.js for the editor page."""
    base = _head(title)
    return Head(
        *base.children,
        Link(rel="stylesheet", href="https://cdn.quilljs.com/2.0.3/quill.snow.css"),
        Script(src="https://cdn.quilljs.com/2.0.3/quill.js"),
        Script(src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"),
    )


# ── List page ──────────────────────────────────────────────────────────


@rt("/app/instructions", methods=["GET"])
def instructions_home(sess):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []

    items = []
    for a in AGENTS:
        path = PROMPTS_DIR / f"{a.slug}.md"
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        vc = count_prompt_versions(a.slug)
        version_badge = Span(f"v{vc}", cls="instr-version-badge") if vc else ""
        items.append(A(
            Div(
                Span(a.icon, cls="instr-icon"),
                Div(
                    Div(a.name, cls="instr-name"),
                    Div(a.one_liner, cls="instr-sub"),
                ),
                version_badge,
                Span(f"{size}b" if exists else "missing", cls="instr-size"),
                cls="instr-row",
            ),
            href=f"/app/instructions/{a.slug}",
            cls="instr-link",
        ))

    body = Body(
        signin_overlay(),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="", current_currency=get_currency(sess)),
        Div(
            Div(
                Div(
                    Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    Span("Instructions", cls="chat-header-title"),
                    Span("·", cls="chat-header-dot"),
                    Span(f"{len(AGENTS)} agent prompts", cls="chat-header-agent"),
                    cls="chat-header-left",
                ),
                Div(
                    A("Back to chat", href="/app", cls="back-to-chat-btn"),
                    cls="chat-header-actions",
                ),
                cls="chat-header",
            ),
            Div(
                P("Edit the system prompts that drive each agent. Saves write to "
                  "prompts/system/<slug>.md and are versioned in the database.",
                  cls="instr-intro"),
                A("Edit shared PE glossary",
                  href="/app/instructions/__shared__",
                  cls="instr-shared-link"),
                *items,
                cls="instr-list",
            ),
            cls="center-pane",
        ),
        Script(src=_versioned("chat.js")),
        cls="bg-bg text-ink font-sans antialiased app pane-closed pipeline-app",
    )
    return Html(_head("Instructions"), body, lang="en")


# ── Editor page ────────────────────────────────────────────────────────


@rt("/app/instructions/{slug}", methods=["GET"])
def instruction_edit(sess, slug: str):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []

    if slug == "__shared__":
        path = SHARED_DIR / "pe_context.md"
        title = "Shared PE glossary"
        subtitle = "Prepended to every agent's system prompt"
    else:
        spec = AGENTS_BY_SLUG.get(slug)
        if not spec:
            return Html(_head("Not found"),
                        Body(Div(H1("Agent not found"),
                                 A("Back", href="/app/instructions"),
                                 cls="p-10 text-ink")))
        path = PROMPTS_DIR / f"{slug}.md"
        title = spec.name
        subtitle = spec.one_liner

    content = path.read_text() if path.exists() else ""
    vc = count_prompt_versions(slug)

    body = Body(
        signin_overlay(),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="", current_currency=get_currency(sess)),
        Div(
            Div(
                Div(
                    Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    A("← Instructions", href="/app/instructions", cls="back-to-chat-btn"),
                    Span("·", cls="chat-header-dot"),
                    Span(title, cls="chat-header-title"),
                    Span(f"v{vc}", cls="instr-version-badge", id="version-badge") if vc else
                    Span("", cls="instr-version-badge", id="version-badge"),
                    cls="chat-header-left",
                ),
                cls="chat-header",
            ),
            Div(
                P(subtitle, cls="instr-sub-big"),
                # Tab bar
                Div(
                    Button("Editor", cls="instr-tab active", id="tab-editor",
                           onclick="switchTab('editor')"),
                    Button("Markdown", cls="instr-tab", id="tab-markdown",
                           onclick="switchTab('markdown')"),
                    Button("History", cls="instr-tab", id="tab-history",
                           onclick="switchTab('history')"),
                    cls="instr-tab-bar",
                ),
                # Hidden textarea holding the markdown source of truth
                Textarea(content, name="content", id="instr-markdown-src",
                         style="display:none"),
                # Editor pane (Quill)
                Div(id="instr-editor-pane", cls="instr-pane"),
                # Markdown pane (raw textarea)
                Div(
                    Textarea(content, id="instr-markdown-textarea",
                             cls="instr-textarea", spellcheck="false", rows="28"),
                    id="instr-markdown-pane", cls="instr-pane", style="display:none",
                ),
                # History pane
                Div(id="instr-history-pane", cls="instr-pane", style="display:none"),
                # Actions
                Div(
                    Div(id="save-status", cls="save-status"),
                    Button("Save", type="button", cls="chat-send instr-save",
                           onclick="savePrompt()"),
                    A("Cancel", href="/app/instructions", cls="back-to-chat-btn"),
                    cls="instr-actions",
                ),
                Input(type="hidden", id="instr-slug", value=slug),
                cls="instr-edit",
            ),
            cls="center-pane",
        ),
        Script(src=_versioned("chat.js")),
        Script(src="/static/instructions.js"),
        cls="bg-bg text-ink font-sans antialiased app pane-closed pipeline-app",
    )
    return Html(_editor_head(f"Edit — {title}"), body, lang="en")


# ── Save endpoint ──────────────────────────────────────────────────────


@rt("/app/instructions/{slug}", methods=["POST"])
async def instruction_save(request: Request, slug: str):
    data = await request.json()
    content = data.get("content") or ""

    if slug == "__shared__":
        path = SHARED_DIR / "pe_context.md"
    else:
        if slug not in AGENTS_BY_SLUG:
            return JSONResponse({"ok": False, "error": "Unknown agent"})
        path = PROMPTS_DIR / f"{slug}.md"

    path.write_text(content)
    version_id = save_prompt_version(slug, content)
    vc = count_prompt_versions(slug)

    try:
        from agents.base import cached_agent
        cached_agent.cache_clear()
    except Exception:
        pass

    return JSONResponse({"ok": True, "version_count": vc, "version_id": version_id})


# ── Version API ────────────────────────────────────────────────────────


@rt("/app/api/prompt-versions/{slug}", methods=["GET"])
def api_prompt_versions(slug: str):
    versions = get_prompt_versions(slug)
    return JSONResponse({"slug": slug, "versions": versions})


@rt("/app/api/prompt-version/{version_id:int}", methods=["GET"])
def api_prompt_version(version_id: int):
    ver = get_prompt_version(version_id)
    if not ver:
        return JSONResponse({"error": "Version not found"}, status_code=404)
    return JSONResponse(ver)


@rt("/app/api/prompt-versions/{slug}/revert", methods=["POST"])
async def api_revert_prompt(request: Request, slug: str):
    data = await request.json()
    version_id = data.get("version_id")
    if not version_id:
        return JSONResponse({"ok": False, "error": "Missing version_id"})

    ver = get_prompt_version(version_id)
    if not ver or ver["slug"] != slug:
        return JSONResponse({"ok": False, "error": "Version not found or slug mismatch"})

    if slug == "__shared__":
        path = SHARED_DIR / "pe_context.md"
    else:
        if slug not in AGENTS_BY_SLUG:
            return JSONResponse({"ok": False, "error": "Unknown agent"})
        path = PROMPTS_DIR / f"{slug}.md"

    path.write_text(ver["content"])
    save_prompt_version(slug, ver["content"], changed_by=f"revert-from-v{version_id}")
    vc = count_prompt_versions(slug)

    try:
        from agents.base import cached_agent
        cached_agent.cache_clear()
    except Exception:
        pass

    return JSONResponse({"ok": True, "version_count": vc, "content": ver["content"]})
