"""Company Search page — fuzzy name search + sector filter, FastHTML table.

/app/companies                → search form + results table
/app/companies/<slug>         → redirect to pipeline deal detail
"""

from __future__ import annotations

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Div, Span, H2, H3, P, A, Button, Form, Input, Select, Option,
    Table, Thead, Tbody, Tr, Th, Td,
)
from starlette.responses import RedirectResponse

from app import rt
from chat.components import left_pane, signin_overlay
from chat.layout import _versioned, common_scripts
from utils.session import get_currency, currency_symbol
from utils.i18n import t, get_lang
from chat.routes import _ensure_user, _list_sessions
from db import connect, fetch_all
from landing.components import TAILWIND_CONFIG, _favicon_links


def _head(title: str):
    return Head(
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Title(f"{title} · PEHero"),
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


def _fmt_revenue(val, sym: str = "€") -> str:
    if not val:
        return "—"
    v = float(val)
    if v >= 1_000_000:
        return f"{sym}{v / 1_000_000:,.1f}M"
    if v >= 1_000:
        return f"{sym}{v / 1_000:,.0f}K"
    return f"{sym}{v:,.0f}"


def _fmt_int(val) -> str:
    if not val:
        return "—"
    return f"{int(val):,}"


def _stage_badge(stage: str) -> Span:
    colors = {
        "sourced": "#9CA89E", "screened": "#7A9E88", "loi": "#C89B5B",
        "diligence": "#B57D3E", "ic": "#4A8E66", "signed": "#2F7151",
        "closed": "#1F5D43", "held": "#3C5748", "exited": "#6B4E2F", "passed": "#9C8F7A",
    }
    color = colors.get(stage, "#9CA89E")
    return Span(
        (stage or "sourced").replace("_", " ").title(),
        style=f"background:{color}; color:white; padding:2px 8px; border-radius:4px; font-size:.68rem; font-weight:600; text-transform:uppercase; letter-spacing:.06em;",
    )


@rt("/app/companies")
def companies_home(sess, q: str = "", sector: str = ""):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)
    sym = currency_symbol(get_currency(sess))

    # Build query
    sql_parts = ["SELECT slug, name, hq_city, country, sector, sub_sector, employees,",
                 "revenue_ltm, ebitda_ltm, ebitda_margin, deal_stage, founded_year",
                 "FROM pehero.companies WHERE TRUE"]
    params: list = []

    if q:
        sql_parts.append("AND name ILIKE %s")
        params.append(f"%{q}%")
    if sector:
        sql_parts.append("AND sector = %s")
        params.append(sector)

    sql_parts.append("ORDER BY revenue_ltm DESC NULLS LAST LIMIT 200")
    rows = fetch_all(" ".join(sql_parts), tuple(params))

    # Get distinct sectors for the filter dropdown
    sectors = fetch_all("SELECT DISTINCT sector FROM pehero.companies ORDER BY sector")
    sector_list = [r["sector"] for r in sectors if r["sector"]]

    # Search form
    search_form = Form(
        Div(
            Input(type="text", name="q", value=q,
                  placeholder=t("search_placeholder", lang),
                  cls="search-input"),
            Select(
                Option(t("search_all_sectors", lang), value="", selected=not sector),
                *[Option(s.replace("_", " ").title(), value=s, selected=s == sector)
                  for s in sector_list],
                name="sector", cls="search-select",
            ),
            Button(t("search_btn", lang), type="submit", cls="search-submit"),
            cls="search-bar",
        ),
        method="get", action="/app/companies",
    )

    # Results table
    if rows:
        result_count = Div(
            Span(t("search_results", lang).format(n=len(rows)), cls="search-count"),
            cls="search-meta",
        )
        table = Table(
            Thead(Tr(
                Th(t("search_col_name", lang)),
                Th(t("search_col_city", lang)),
                Th(t("search_col_sector", lang)),
                Th(t("search_col_revenue", lang), cls="text-right"),
                Th(t("search_col_ebitda", lang), cls="text-right"),
                Th(t("search_col_employees", lang), cls="text-right"),
                Th(t("search_col_stage", lang)),
            )),
            Tbody(
                *[Tr(
                    Td(A(r["name"], href=f"/app/pipeline/{r['slug']}", cls="company-link")),
                    Td(r["hq_city"] or "—"),
                    Td(Span((r["sector"] or "").replace("_", " ").title(), cls="sector-chip")),
                    Td(_fmt_revenue(r["revenue_ltm"], sym), cls="text-right mono"),
                    Td(_fmt_revenue(r["ebitda_ltm"], sym), cls="text-right mono"),
                    Td(_fmt_int(r["employees"]), cls="text-right mono"),
                    Td(_stage_badge(r["deal_stage"])),
                    cls="search-row",
                ) for r in rows],
            ),
            cls="search-table",
        )
    else:
        result_count = None
        table = Div(
            P(t("search_no_results", lang), cls="search-empty"),
        )

    body = Body(
        signin_overlay(lang=lang),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="",
                  current_currency=get_currency(sess),
                  current_path="/app/companies", lang=lang),
        Div(
            Div(
                Div(
                    Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    Span(t("search_title", lang), cls="chat-header-title"),
                    Span("·", cls="chat-header-dot"),
                    Span(t("search_results", lang).format(n=len(rows)) if rows else "",
                         cls="chat-header-agent"),
                    cls="chat-header-left",
                ),
                Div(
                    A(t("chat_back", lang), href="/app", cls="back-to-chat-btn"),
                    cls="chat-header-actions",
                ),
                cls="chat-header",
            ),
            Div(
                search_form,
                result_count,
                table,
                cls="companies-wrap",
            ),
            cls="center-pane pipeline-center",
        ),
        Script(src=_versioned("chat.js")),
        cls="bg-bg text-ink font-sans antialiased app pane-closed pipeline-app",
    )
    return Html(_head(t("search_title", lang)), body, lang=lang)
