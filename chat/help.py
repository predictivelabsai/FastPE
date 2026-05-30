"""Help / User Guide page — renders docs/user_guide.md as a FastHTML page
with a sticky TOC at the top.

/app/help → rendered user guide
"""

from __future__ import annotations

import re
from pathlib import Path

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Div, Span, H1, H2, H3, H4, P, A, Button, Img, Table, Thead, Tbody, Tr, Th, Td,
    Ul, Li, Hr, Nav,
)

from app import rt
from chat.components import left_pane, signin_overlay
from chat.layout import _versioned, common_scripts
from utils.session import get_currency
from utils.i18n import t, get_lang
from chat.routes import _ensure_user, _list_sessions
from landing.components import TAILWIND_CONFIG, _favicon_links

_GUIDE_PATH = Path(__file__).resolve().parent.parent / "docs" / "user_guide.md"


def _head():
    return Head(
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Title("User Guide · PEHero"),
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


def _extract_toc(md: str) -> list[tuple[str, str]]:
    """Extract ## headings for table of contents."""
    toc = []
    for line in md.split("\n"):
        line = line.strip()
        if line.startswith("## ") and not line.startswith("## Table of Contents"):
            title = line[3:]
            slug = _slugify(title)
            toc.append((title, slug))
    return toc


def _build_toc(toc: list[tuple[str, str]]) -> Nav:
    """Build a horizontal TOC nav bar."""
    links = [A(title, href=f"#{slug}", cls="guide-toc-link") for title, slug in toc]
    return Nav(
        Div(*links, cls="guide-toc-links"),
        cls="guide-toc",
    )


def _md_to_components(md: str) -> list:
    """Convert markdown to FastHTML components (skips TOC section)."""
    import html as _html

    elements = []
    lines = md.split("\n")
    i = 0
    in_table = False
    table_rows = []
    in_list = False
    list_items = []
    in_code = False
    code_lines = []
    skip_toc = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip the markdown TOC section
        if stripped == "## Table of Contents":
            skip_toc = True
            i += 1
            continue
        if skip_toc:
            if stripped.startswith("## ") and stripped != "## Table of Contents":
                skip_toc = False
            elif stripped.startswith("---"):
                skip_toc = False
                i += 1
                continue
            else:
                i += 1
                continue

        # Code blocks
        if stripped.startswith("```"):
            if in_code:
                from fasthtml.common import Pre, Code
                elements.append(Pre(Code("\n".join(code_lines)), cls="guide-code"))
                code_lines = []
                in_code = False
            else:
                if in_list:
                    elements.append(Ul(*list_items, cls="guide-list"))
                    list_items = []
                    in_list = False
                in_code = True
            i += 1
            continue

        if in_code:
            code_lines.append(line)
            i += 1
            continue

        # Table rows
        if stripped.startswith("|") and stripped.endswith("|"):
            if re.fullmatch(r"\|[\s\-:|]+\|", stripped):
                i += 1
                continue
            cells = [c.strip() for c in stripped[1:-1].split("|")]
            if not in_table:
                if in_list:
                    elements.append(Ul(*list_items, cls="guide-list"))
                    list_items = []
                    in_list = False
                in_table = True
                table_rows = []
            table_rows.append(cells)
            i += 1
            continue

        if in_table:
            header = table_rows[0] if table_rows else []
            body = table_rows[1:] if len(table_rows) > 1 else []
            elements.append(
                Div(
                    Table(
                        Thead(Tr(*[Th(c) for c in header])) if header else None,
                        Tbody(*[Tr(*[Td(NotStr(_inline_md(c))) for c in row]) for row in body]),
                        cls="search-table",
                    ),
                    cls="guide-table-wrap",
                )
            )
            table_rows = []
            in_table = False

        # Numbered lists
        m_num = re.match(r"^(\d+)\.\s+(.+)", stripped)
        if m_num:
            if not in_list:
                in_list = True
            list_items.append(Li(NotStr(_inline_md(m_num.group(2)))))
            i += 1
            continue

        # Bullet lists
        if stripped.startswith("- "):
            if not in_list:
                in_list = True
            list_items.append(Li(NotStr(_inline_md(stripped[2:]))))
            i += 1
            continue

        if in_list:
            elements.append(Ul(*list_items, cls="guide-list"))
            list_items = []
            in_list = False

        # Headings
        if stripped.startswith("# ") and not stripped.startswith("## "):
            elements.append(H1(stripped[2:], cls="guide-h1"))
        elif stripped.startswith("### "):
            elements.append(H3(stripped[4:], cls="guide-h3", id=_slugify(stripped[4:])))
        elif stripped.startswith("## "):
            elements.append(H2(stripped[3:], cls="guide-h2", id=_slugify(stripped[3:])))
        elif stripped.startswith("#### "):
            elements.append(H4(stripped[5:], cls="guide-h4"))
        elif stripped == "---":
            elements.append(Hr(cls="guide-hr"))
        elif stripped.startswith("!["):
            m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
            if m:
                alt, src = m.group(1), m.group(2)
                if not src.startswith("http"):
                    src = f"/docs/{src}"
                elements.append(Div(Img(src=src, alt=alt, cls="guide-img"), cls="guide-img-wrap"))
        elif stripped:
            elements.append(P(NotStr(_inline_md(stripped)), cls="guide-p"))

        i += 1

    if in_list:
        elements.append(Ul(*list_items, cls="guide-list"))
    if in_table and table_rows:
        header = table_rows[0]
        body = table_rows[1:]
        elements.append(
            Table(
                Thead(Tr(*[Th(c) for c in header])),
                Tbody(*[Tr(*[Td(NotStr(_inline_md(c))) for c in row]) for row in body]),
                cls="search-table",
            )
        )

    return elements


def _inline_md(text: str) -> str:
    import html as _html
    text = _html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r'<code class="guide-inline-code">\1</code>', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" class="guide-link">\1</a>', text)
    return text


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


@rt("/app/help")
def help_page(sess):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)

    md = _GUIDE_PATH.read_text() if _GUIDE_PATH.exists() else "# User Guide\n\nContent coming soon."
    toc = _extract_toc(md)
    toc_nav = _build_toc(toc)
    content = _md_to_components(md)

    body = Body(
        signin_overlay(lang=lang),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="",
                  current_currency=get_currency(sess),
                  current_path="/app/help", lang=lang),
        Div(
            Div(
                Div(
                    Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    Span(t("help_title", lang), cls="chat-header-title"),
                    cls="chat-header-left",
                ),
                Div(
                    A(t("chat_back", lang), href="/app", cls="back-to-chat-btn"),
                    cls="chat-header-actions",
                ),
                cls="chat-header",
            ),
            Div(
                toc_nav,
                Div(*content, cls="guide-content"),
                cls="companies-wrap",
            ),
            cls="center-pane pipeline-center",
        ),
        Script(src=_versioned("chat.js")),
        cls="bg-bg text-ink font-sans antialiased app pane-closed pipeline-app",
    )
    return Html(_head(), body, lang=lang)
