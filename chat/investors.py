"""Investors page — family office & investor prospecting.

/app/investors              → search/filter list of persons (owners, directors, HNW)
/app/investors/<slug>       → person detail with company portfolio
"""

from __future__ import annotations

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Div, Span, H2, H3, P, A, Button, Form, Input, Select, Option, Small,
    Table, Thead, Tbody, Tr, Th, Td,
)

from app import rt
from chat.components import left_pane, signin_overlay, copilot_pane, copilot_toggle_btn
from chat.layout import _versioned, common_scripts
from utils.session import get_currency, currency_symbol
from utils.i18n import t, get_lang
from chat.routes import _ensure_user, _list_sessions
from db import connect, fetch_all, fetch_one
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


def _fmt_wealth(val) -> str:
    if not val:
        return "—"
    v = float(val)
    if v >= 1_000_000_000:
        return f"€{v / 1_000_000_000:,.1f}B"
    if v >= 1_000_000:
        return f"€{v / 1_000_000:,.1f}M"
    if v >= 1_000:
        return f"€{v / 1_000:,.0f}K"
    return f"€{v:,.0f}"


def _wealth_badge(wealth_eur, rank) -> Span:
    if not wealth_eur:
        return Span("—", cls="wealth-badge unknown")
    v = float(wealth_eur)
    if v >= 100_000_000:
        tier = "ultra"
    elif v >= 10_000_000:
        tier = "high"
    elif v >= 1_000_000:
        tier = "mid"
    else:
        tier = "low"
    label = _fmt_wealth(wealth_eur)
    if rank:
        label += f" #{rank}"
    return Span(label, cls=f"wealth-badge {tier}")


def _sector_chips(sectors) -> list:
    if not sectors:
        return [Span("—")]
    chips = []
    for s in sectors[:3]:
        if chips:
            chips.append(Span(" "))
        chips.append(Span(s.replace("_", " ").title(), cls="sector-chip"))
    return chips


@rt("/app/investors")
def investors_home(sess, q: str = "", wealth: str = "", sector: str = "", min_companies: int = 0):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)

    sql_parts = ["""
        SELECT p.slug, p.name, p.country, p.wealth_eur, p.wealth_rank,
               p.wealth_source, p.sector_exposure,
               COUNT(pcl.id) AS company_count,
               MAX(pcl.stake_pct) AS max_stake
        FROM pehero.persons p
        LEFT JOIN pehero.person_company_links pcl ON pcl.person_id = p.id
        WHERE TRUE
    """]
    params: list = []

    if q:
        sql_parts.append("AND p.name ILIKE %s")
        params.append(f"%{q}%")
    if wealth == "100m":
        sql_parts.append("AND p.wealth_eur >= 100000000")
    elif wealth == "10m":
        sql_parts.append("AND p.wealth_eur >= 10000000 AND p.wealth_eur < 100000000")
    elif wealth == "1m":
        sql_parts.append("AND p.wealth_eur >= 1000000 AND p.wealth_eur < 10000000")
    elif wealth == "known":
        sql_parts.append("AND p.wealth_eur IS NOT NULL")
    if sector:
        sql_parts.append("AND %s = ANY(p.sector_exposure)")
        params.append(sector)

    sql_parts.append("""
        GROUP BY p.id
        HAVING COUNT(pcl.id) >= %s
        ORDER BY p.wealth_eur DESC NULLS LAST, company_count DESC
        LIMIT 200
    """)
    params.append(min_companies)

    rows = fetch_all(" ".join(sql_parts), tuple(params))

    # Get distinct sectors for filter
    sector_rows = fetch_all("""
        SELECT DISTINCT unnest(sector_exposure) AS sec FROM pehero.persons ORDER BY sec
    """)
    sector_list = [r["sec"] for r in sector_rows if r["sec"]]

    search_form = Form(
        Div(
            Input(type="text", name="q", value=q,
                  placeholder=t("inv_search_placeholder", lang),
                  cls="search-input"),
            Select(
                Option(t("inv_wealth_all", lang), value="", selected=not wealth),
                Option("€100M+", value="100m", selected=wealth == "100m"),
                Option("€10M–100M", value="10m", selected=wealth == "10m"),
                Option("€1M–10M", value="1m", selected=wealth == "1m"),
                Option(t("inv_wealth_known", lang), value="known", selected=wealth == "known"),
                name="wealth", cls="search-select",
            ),
            Select(
                Option(t("search_all_sectors", lang), value="", selected=not sector),
                *[Option(s.replace("_", " ").title(), value=s, selected=s == sector)
                  for s in sector_list],
                name="sector", cls="search-select",
            ),
            Button(t("search_btn", lang), type="submit", cls="search-submit"),
            cls="search-bar",
        ),
        method="get", action="/app/investors",
    )

    if rows:
        result_count = Div(
            Span(t("inv_results", lang).format(n=len(rows)), cls="search-count"),
            cls="search-meta",
        )
        table = Table(
            Thead(Tr(
                Th(t("inv_col_name", lang)),
                Th(t("inv_col_companies", lang), cls="text-right"),
                Th(t("inv_col_top_stake", lang), cls="text-right"),
                Th(t("inv_col_wealth", lang)),
                Th(t("inv_col_sectors", lang)),
                Th(t("inv_col_country", lang)),
            )),
            Tbody(
                *[Tr(
                    Td(A(r["name"], href=f"/app/investors/{r['slug']}", cls="company-link")),
                    Td(str(r["company_count"]), cls="text-right mono"),
                    Td(f"{float(r['max_stake']):.1f}%" if r["max_stake"] else "—", cls="text-right mono"),
                    Td(_wealth_badge(r["wealth_eur"], r["wealth_rank"])),
                    Td(*_sector_chips(r["sector_exposure"])),
                    Td(r["country"] or "—"),
                    cls="search-row",
                ) for r in rows],
            ),
            cls="search-table",
        )
    else:
        result_count = None
        table = Div(P(t("inv_no_results", lang), cls="search-empty"))

    body = Body(
        signin_overlay(lang=lang),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="",
                  current_currency=get_currency(sess),
                  current_path="/app/investors", lang=lang),
        Div(
            Div(
                Div(
                    Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    Span(t("inv_title", lang), cls="chat-header-title"),
                    Span("·", cls="chat-header-dot"),
                    Span(t("inv_results", lang).format(n=len(rows)) if rows else "",
                         cls="chat-header-agent"),
                    cls="chat-header-left",
                ),
                Div(
                    copilot_toggle_btn(lang=lang),
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
        copilot_pane(
            page_name="Investors",
            page_context={
                "page": "Investors",
                "search_query": q,
                "wealth_filter": wealth,
                "sector_filter": sector,
                "results_count": len(rows),
            },
            lang=lang,
        ),
        Script(src=_versioned("chat.js")),
        Script(src=_versioned("copilot.js")),
        cls="bg-bg text-ink font-sans antialiased app pipeline-app",
    )
    return Html(_head(t("inv_title", lang)), body, lang=lang)


@rt("/app/investors/{slug}")
def investor_detail(sess, slug: str):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)
    sym = currency_symbol(get_currency(sess))

    person = fetch_one("SELECT * FROM pehero.persons WHERE slug = %s", (slug,))
    if not person:
        return Html(_head("Not found"), Body(P("Person not found.")))

    links = fetch_all("""
        SELECT pcl.*, c.slug AS company_slug, c.sector, c.revenue_ltm, c.employees
        FROM pehero.person_company_links pcl
        LEFT JOIN pehero.companies c ON c.id = pcl.company_id
        WHERE pcl.person_id = %s
        ORDER BY pcl.stake_pct DESC NULLS LAST, pcl.company_name
    """, (person["id"],))

    # Person header
    wealth_str = _fmt_wealth(person["wealth_eur"])
    rank_str = f" (#{person['wealth_rank']})" if person["wealth_rank"] else ""
    source_str = person["wealth_source"] or ""

    header = Div(
        Div(
            A("← " + t("inv_title", lang), href="/app/investors", cls="back-link"),
            cls="detail-back",
        ),
        Div(
            H2(person["name"], cls="detail-name"),
            Div(
                Span(person["country"] or "EE", cls="country-badge"),
                Span(f"{wealth_str}{rank_str}", cls="wealth-badge high" if person["wealth_eur"] else "wealth-badge unknown"),
                Small(source_str, cls="wealth-source") if source_str else "",
                cls="detail-meta",
            ),
            Div(
                *_sector_chips(person["sector_exposure"]),
                cls="detail-sectors",
            ),
            cls="detail-header-info",
        ),
        cls="detail-header",
    )

    # Portfolio table
    if links:
        portfolio = Table(
            Thead(Tr(
                Th(t("inv_col_company", lang)),
                Th(t("inv_col_role", lang)),
                Th(t("inv_col_stake", lang), cls="text-right"),
                Th(t("inv_col_sector_detail", lang)),
                Th(t("inv_col_control", lang)),
            )),
            Tbody(
                *[Tr(
                    Td(A(lk["company_name"],
                         href=f"/app/pipeline/{lk['company_slug']}" if lk.get("company_slug") else "#",
                         cls="company-link")),
                    Td(Span(lk["role"].replace("_", " ").title(),
                            cls="role-chip")),
                    Td(f"{float(lk['stake_pct']):.1f}%" if lk["stake_pct"] else "—",
                       cls="text-right mono"),
                    Td((lk.get("sector") or "").replace("_", " ").title() or "—"),
                    Td(lk["control_desc"] or "—", cls="control-text"),
                    cls="search-row",
                ) for lk in links],
            ),
            cls="search-table",
        )
    else:
        portfolio = Div(P("No company links found.", cls="search-empty"))

    body = Body(
        signin_overlay(lang=lang),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="",
                  current_currency=get_currency(sess),
                  current_path="/app/investors", lang=lang),
        Div(
            Div(
                Div(
                    Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    Span(person["name"], cls="chat-header-title"),
                    cls="chat-header-left",
                ),
                Div(
                    copilot_toggle_btn(lang=lang),
                    cls="chat-header-actions",
                ),
                cls="chat-header",
            ),
            Div(
                header,
                H3(t("inv_portfolio", lang), cls="section-title"),
                portfolio,
                cls="companies-wrap",
            ),
            cls="center-pane pipeline-center",
        ),
        copilot_pane(
            page_name="Investor Detail",
            page_context={
                "page": "Investor Detail",
                "person_name": person["name"],
                "company_count": len(links),
            },
            lang=lang,
        ),
        Script(src=_versioned("chat.js")),
        Script(src=_versioned("copilot.js")),
        cls="bg-bg text-ink font-sans antialiased app pipeline-app",
    )
    return Html(_head(person["name"]), body, lang=lang)
