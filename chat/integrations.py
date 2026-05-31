"""Integrations page — tabbed dashboard for CRM + Data Sources.

/app/integrations                → overview (both sections)
/app/integrations/connect        → save Pipedrive token (POST)
/app/integrations/disconnect     → remove Pipedrive token (POST)
/app/integrations/sync           → trigger Pipedrive sync (POST)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Div, Span, H2, H3, H4, P, A, Button, Form, Input, Select, Option, Small,
    Table, Thead, Tbody, Tr, Th, Td, Details, Summary,
)
from starlette.responses import JSONResponse

from app import rt
from chat.components import left_pane, signin_overlay, copilot_pane, copilot_toggle_btn
from chat.layout import _versioned, common_scripts
from utils.session import get_currency, currency_symbol
from utils.i18n import t, get_lang
from utils.config import settings
from chat.routes import _ensure_user, _list_sessions
from db import fetch_all, fetch_one
from landing.components import TAILWIND_CONFIG, _favicon_links
from tools.pipedrive import get_user_token, save_user_token, delete_user_token, test_connection


def _head():
    return Head(
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Title("Integrations · PEHero"),
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


def _fmt_num(n) -> str:
    if n is None:
        return "—"
    return f"{int(n):,}"


def _time_ago(dt) -> str:
    if not dt:
        return "never"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return dt
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    mins = int((now - dt).total_seconds() / 60)
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def _status_badge(connected: bool) -> Span:
    if connected:
        return Span("Connected", style="background:#1F5D43; color:white; padding:2px 10px; border-radius:4px; font-size:.72rem; font-weight:600;")
    return Span("Not configured", style="background:#9CA89E; color:white; padding:2px 10px; border-radius:4px; font-size:.72rem; font-weight:600;")


def _data_badge(has_data: bool) -> Span:
    if has_data:
        return Span("Active", style="background:#1F5D43; color:white; padding:2px 10px; border-radius:4px; font-size:.72rem; font-weight:600;")
    return Span("No data", style="background:#9CA89E; color:white; padding:2px 10px; border-radius:4px; font-size:.72rem; font-weight:600;")


def _stage_badge(stage: str) -> Span:
    colors = {
        "sourced": "#9CA89E", "screened": "#7A9E88", "outreach": "#6A9E78",
        "meeting": "#5A8E68", "loi": "#C89B5B", "dd": "#B57D3E",
        "ic": "#4A8E66", "closing": "#2F7151",
        "cold": "#9CA89E", "qualified": "#7A9E88", "committed": "#4A8E66",
        "closed": "#1F5D43", "passed": "#6B4E2F",
    }
    color = colors.get(stage, "#9CA89E")
    return Span(
        (stage or "—").replace("_", " ").title(),
        style=f"background:{color}; color:white; padding:2px 8px; border-radius:4px; font-size:.66rem; font-weight:600; text-transform:uppercase; letter-spacing:.06em;",
    )


def _user_pd_connected(uid: int | None) -> tuple[bool, str]:
    if uid:
        row = get_user_token(uid)
        if row and row["api_token"]:
            return True, row["domain"] or ""
    s = settings()
    if s.pipedrive_api_token:
        return True, s.pipedrive_domain or ""
    return False, ""


# ── Data source definitions ──────────────────────────────────────────

DATA_SOURCES = [
    {
        "key": "EE", "country": "Estonia", "flag": "🇪🇪",
        "name": "Teatmik / SSB.ee",
        "url": "https://ssb.ee",
        "description": "Estonian company register with financial statements. Scraped by sector (EMTAK classification).",
        "fields": ["name", "registry_code", "address", "founded", "employees",
                   "revenue", "net_profit", "equity", "total_assets", "EMTAK sector"],
        "license": "Public data",
    },
    {
        "key": "LT", "country": "Lithuania", "flag": "🇱🇹",
        "name": "Rekvizitai.vz.lt",
        "url": "https://rekvizitai.vz.lt",
        "description": "Lithuanian business information portal. Company financials, credit scores, and management data.",
        "fields": ["name", "reg_code", "VAT", "address", "employees", "avg_salary",
                   "revenue", "net_profit", "credit_risk", "manager", "share_capital"],
        "license": "Public data",
    },
    {
        "key": "LV", "country": "Latvia", "flag": "🇱🇻",
        "name": "data.gov.lv (CKAN)",
        "url": "https://data.gov.lv",
        "description": "Latvian open data portal. Pure REST API (no scraping). Joins 5 datasets: companies, financials, employees, addresses, NACE codes. CC0 license.",
        "fields": ["name", "reg_code", "address", "founded", "employees",
                   "revenue", "net_profit", "gross_profit", "total_assets",
                   "equity", "liabilities", "cash_flow", "NACE sector"],
        "license": "CC0 Open Data",
    },
    {
        "key": "RO", "country": "Romania", "flag": "🇷🇴",
        "name": "ONRC + ANAF Bilant",
        "url": "https://data.gov.ro",
        "description": "Two-step: ONRC company registry CSV from data.gov.ro, enriched with ANAF financial statements via REST API. CAEN sector classification.",
        "fields": ["name", "CUI", "county", "locality", "CAEN sector",
                   "revenue", "net_profit", "gross_profit", "total_assets", "employees"],
        "license": "Public API (1 req/s)",
    },
    {
        "key": "PL", "country": "Poland", "flag": "🇵🇱",
        "name": "KRS Open API",
        "url": "https://api-krs.ms.gov.pl",
        "description": "Polish National Court Register (KRS) open API. Registration data only — financials require paid services (Transparent Data / Apify).",
        "fields": ["name", "KRS_number", "NIP", "REGON", "address",
                   "PKD sector", "share_capital", "board_members"],
        "license": "Public API",
    },
]


def _get_country_stats() -> dict:
    """Fetch per-country company and financial stats from DB."""
    rows = fetch_all(
        "SELECT country, count(*) as companies, "
        "count(revenue_ltm) as with_revenue, "
        "coalesce(avg(revenue_ltm)::bigint, 0) as avg_revenue, "
        "coalesce(max(revenue_ltm)::bigint, 0) as max_revenue, "
        "coalesce(avg(employees)::int, 0) as avg_employees "
        "FROM pehero.companies GROUP BY country"
    )
    stats = {}
    for r in rows:
        stats[r["country"]] = r

    fin_rows = fetch_all(
        "SELECT c.country, count(f.id) as fin_rows "
        "FROM pehero.financials f JOIN pehero.companies c ON c.id = f.company_id "
        "GROUP BY c.country"
    )
    for r in fin_rows:
        if r["country"] in stats:
            stats[r["country"]]["fin_rows"] = r["fin_rows"]

    return stats


def _build_data_source_card(src: dict, stats: dict, sym: str) -> Div:
    """Build a card for one data source."""
    cs = stats.get(src["key"], {})
    n_companies = cs.get("companies", 0)
    has_data = n_companies > 0

    stat_items = []
    if has_data:
        stat_items = [
            Div(Span("Companies", cls="stat-label"),
                Span(_fmt_num(n_companies), cls="stat-value"),
                cls="stat-item"),
            Div(Span("With revenue", cls="stat-label"),
                Span(_fmt_num(cs.get("with_revenue", 0)), cls="stat-value"),
                cls="stat-item"),
            Div(Span("Avg revenue", cls="stat-label"),
                Span(_fmt_revenue(cs.get("avg_revenue"), sym), cls="stat-value mono"),
                cls="stat-item"),
            Div(Span("Largest", cls="stat-label"),
                Span(_fmt_revenue(cs.get("max_revenue"), sym), cls="stat-value mono"),
                cls="stat-item"),
            Div(Span("Financial rows", cls="stat-label"),
                Span(_fmt_num(cs.get("fin_rows", 0)), cls="stat-value"),
                cls="stat-item"),
            Div(Span("Avg employees", cls="stat-label"),
                Span(_fmt_num(cs.get("avg_employees")) if cs.get("avg_employees") else "—", cls="stat-value"),
                cls="stat-item"),
        ]

    fields_str = ", ".join(src["fields"][:8])
    if len(src["fields"]) > 8:
        fields_str += f" +{len(src['fields']) - 8} more"

    return Div(
        Div(
            H4(
                Span(src["flag"], style="margin-right:.4rem;"),
                f"{src['country']} — {src['name']}",
            ),
            _data_badge(has_data),
            cls="integration-status-header",
        ),
        P(src["description"],
          style="font-size:.76rem; color:var(--ink-muted); margin:.3rem 0;"),
        Div(
            Span("Source: ", style="font-weight:600;"),
            A(src["url"], href=src["url"], target="_blank",
              style="color:var(--accent); text-decoration:none;"),
            Span(f" · {src['license']}", style="color:var(--ink-dim);"),
            style="font-size:.7rem; margin-bottom:.3rem;",
        ),
        Div(
            Span("Fields: ", style="font-weight:600;"),
            Span(fields_str, cls="mono", style="color:var(--ink-muted);"),
            style="font-size:.68rem; margin-bottom:.5rem;",
        ),
        Div(*stat_items, cls="integration-stats") if stat_items else
        P("No data loaded yet. Run the scraper to populate.",
          style="font-size:.72rem; color:var(--ink-dim); font-style:italic; margin:.4rem 0;"),
        cls="integration-card",
    )


# ── Pipedrive section ────────────────────────────────────────────────

def _build_pipedrive_section(uid, pd_connected, pd_domain, sync_stats, companies, lps, sequences, sym):
    """Build the full Pipedrive CRM section."""
    if pd_connected:
        status_card = Div(
            Div(
                H4("Connection"),
                _status_badge(True),
                cls="integration-status-header",
            ),
            Div(
                Div(Span("Domain", cls="stat-label"),
                    Span(pd_domain or "not set", cls="stat-value mono"),
                    cls="stat-item"),
                Div(Span("Companies synced", cls="stat-label"),
                    Span(str(sync_stats.get("company", {}).get("count", 0)), cls="stat-value"),
                    cls="stat-item"),
                Div(Span("LPs synced", cls="stat-label"),
                    Span(str(sync_stats.get("investor", {}).get("count", 0)), cls="stat-value"),
                    cls="stat-item"),
                Div(Span("Last sync", cls="stat-label"),
                    Span(
                        _time_ago(sync_stats.get("company", {}).get("last_sync"))
                        if sync_stats.get("company") else "never",
                        cls="stat-value"),
                    cls="stat-item"),
                cls="integration-stats",
            ),
            Div(
                Button("Sync companies →", cls="integration-action-btn",
                       hx_post="/app/integrations/sync?target=companies",
                       hx_swap="none"),
                Button("Sync LPs →", cls="integration-action-btn",
                       hx_post="/app/integrations/sync?target=lps",
                       hx_swap="none"),
                Button("Setup pipelines →", cls="integration-action-btn secondary",
                       hx_post="/app/integrations/sync?target=setup",
                       hx_swap="none"),
                Button("Disconnect", cls="integration-action-btn danger",
                       hx_post="/app/integrations/disconnect",
                       hx_swap="none",
                       hx_confirm="Disconnect your Pipedrive account?"),
                cls="integration-actions",
            ),
            cls="integration-card",
        )
    else:
        status_card = Div(
            Div(
                H4("Connection"),
                _status_badge(False),
                cls="integration-status-header",
            ),
            P("Connect your Pipedrive account by pasting your personal API token. "
              "Find it at Settings → Personal preferences → API.",
              style="font-size:.78rem; color:var(--ink-muted); margin:.5rem 0 .8rem;"),
            Form(
                Div(
                    Div(Span("API Token", cls="stat-label"),
                        Input(type="text", name="api_token",
                              placeholder="e.g. fe5bd40c42dd42ef...",
                              cls="pd-token-input", required=True),
                        cls="pd-field"),
                    Div(Span("Company domain", cls="stat-label"),
                        Input(type="text", name="domain",
                              placeholder="e.g. yourcompany (from yourcompany.pipedrive.com)",
                              cls="pd-token-input", required=True),
                        cls="pd-field"),
                    cls="pd-form-fields",
                ),
                Div(Button("Connect Pipedrive →", type="submit",
                           cls="integration-action-btn"),
                    cls="integration-actions", style="margin-top:.6rem;"),
                Div(id="pd-connect-error", cls="pd-error"),
                hx_post="/app/integrations/connect",
                hx_swap="none",
            ),
            cls="integration-card",
        )

    deal_table = Details(
        Summary(H4(f"Deal Sourcing Pipeline · {len(companies)} companies")),
        Table(
            Thead(Tr(
                Th("Company"), Th("Country"), Th("Sector"),
                Th("Revenue", cls="text-right"), Th("Stage"),
                Th("Pipedrive"), Th("Last sync"),
            )),
            Tbody(*[Tr(
                Td(A(c["name"][:35], href=f"/app/pipeline/{c['slug']}", cls="company-link")),
                Td(c["country"] or "—"),
                Td(Span((c["sector"] or "").replace("_", " ").title(), cls="sector-chip")),
                Td(_fmt_revenue(c["revenue_ltm"], sym), cls="text-right mono"),
                Td(_stage_badge(c["deal_stage"])),
                Td(Span(f"#{c['pipedrive_id']}", cls="mono pd-id") if c["pipedrive_id"]
                   else Span("—", cls="text-muted")),
                Td(_time_ago(c["last_synced"]) if c["last_synced"] else "—"),
                cls="search-row",
            ) for c in companies]),
            cls="search-table",
        ),
        open=pd_connected,
        cls="integration-section",
    )

    lp_table = Details(
        Summary(H4(f"LP Fundraising · {len(lps)} investors")),
        Table(
            Thead(Tr(
                Th("Name"), Th("Firm"), Th("Type"),
                Th("Commitment", cls="text-right"), Th("Stage"),
                Th("Pipedrive"), Th("Last touch"),
            )),
            Tbody(*[Tr(
                Td(lp["name"][:30]),
                Td((lp["firm"] or "—")[:25]),
                Td(Span((lp["lp_type"] or "").replace("_", " ").title(), cls="sector-chip")),
                Td(_fmt_revenue(lp["commitment_size"], sym), cls="text-right mono"),
                Td(_stage_badge(lp["stage"])),
                Td(Span(f"#{lp['pipedrive_id']}", cls="mono pd-id") if lp["pipedrive_id"]
                   else Span("—", cls="text-muted")),
                Td(str(lp["last_touch"]) if lp["last_touch"] else "—"),
                cls="search-row",
            ) for lp in lps]),
            cls="search-table",
        ),
        open=False,
        cls="integration-section",
    )

    seq_items = []
    for s in sequences:
        target = s.get("company_name") or s.get("investor_name") or "Unknown"
        touches = s.get("touches") or []
        if isinstance(touches, str):
            try:
                touches = json.loads(touches)
            except Exception:
                touches = []
        sent = sum(1 for t_ in touches if t_.get("sent"))
        total = len(touches)
        seq_items.append(Tr(
            Td(target[:30]),
            Td(Span(s["sequence_type"].replace("_", " ").title(), cls="sector-chip")),
            Td(_stage_badge(s["status"])),
            Td(f"{sent}/{total}", cls="mono"),
            Td(_time_ago(s["created_at"])),
        ))

    seq_table = Details(
        Summary(H4(f"Outreach Sequences · {len(sequences)}")),
        Table(
            Thead(Tr(Th("Target"), Th("Type"), Th("Status"), Th("Progress"), Th("Created"))),
            Tbody(*seq_items) if seq_items else Tbody(
                Tr(Td("No sequences yet. Use the Outreach Sequencer agent to create one.",
                       colspan="5", cls="text-muted",
                       style="text-align:center; padding:2rem;"))),
            cls="search-table",
        ),
        open=False,
        cls="integration-section",
    )

    return Div(status_card, deal_table, lp_table, seq_table)


# ── Main route ───────────────────────────────────────────────────────

@rt("/app/integrations")
def integrations_home(sess):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)
    sym = currency_symbol(get_currency(sess))

    pd_connected, pd_domain = _user_pd_connected(uid)

    sync_rows = fetch_all(
        "SELECT entity_type, count(*) as n, max(last_synced) as last_sync "
        "FROM pehero.pipedrive_sync GROUP BY entity_type ORDER BY entity_type"
    )
    sync_stats = {r["entity_type"]: {"count": r["n"], "last_sync": r["last_sync"]} for r in sync_rows}

    companies = fetch_all(
        "SELECT c.id, c.slug, c.name, c.country, c.sector, c.revenue_ltm, "
        "c.ebitda_ltm, c.deal_stage, c.hq_city, "
        "ps.pipedrive_id, ps.last_synced "
        "FROM pehero.companies c "
        "LEFT JOIN pehero.pipedrive_sync ps ON ps.entity_type = 'company' AND ps.pehero_id = c.id "
        "WHERE c.deal_stage IS NOT NULL "
        "ORDER BY c.revenue_ltm DESC NULLS LAST LIMIT 100"
    )

    lps = fetch_all(
        "SELECT i.id, i.name, i.firm, i.lp_type, i.stage, i.commitment_size, "
        "i.last_touch, ps.pipedrive_id, ps.last_synced "
        "FROM pehero.investor_crm i "
        "LEFT JOIN pehero.pipedrive_sync ps ON ps.entity_type = 'investor' AND ps.pehero_id = i.id "
        "ORDER BY i.commitment_size DESC NULLS LAST LIMIT 50"
    )

    sequences = fetch_all(
        "SELECT os.id, os.sequence_type, os.status, os.created_at, os.touches, "
        "c.name as company_name, i.name as investor_name "
        "FROM pehero.outreach_sequences os "
        "LEFT JOIN pehero.companies c ON c.id = os.company_id "
        "LEFT JOIN pehero.investor_crm i ON i.id = os.investor_id "
        "ORDER BY os.created_at DESC LIMIT 20"
    )

    country_stats = _get_country_stats()

    # Total stats summary
    total_companies = sum(s.get("companies", 0) for s in country_stats.values())
    total_fin = sum(s.get("fin_rows", 0) for s in country_stats.values())
    active_sources = sum(1 for s in DATA_SOURCES if country_stats.get(s["key"], {}).get("companies", 0) > 0)

    overview_bar = Div(
        Div(Span("Total companies", cls="stat-label"),
            Span(_fmt_num(total_companies), cls="stat-value"),
            cls="stat-item"),
        Div(Span("Active sources", cls="stat-label"),
            Span(f"{active_sources}/{len(DATA_SOURCES)}", cls="stat-value"),
            cls="stat-item"),
        Div(Span("Financial rows", cls="stat-label"),
            Span(_fmt_num(total_fin), cls="stat-value"),
            cls="stat-item"),
        Div(Span("CRM", cls="stat-label"),
            Span("Pipedrive" if pd_connected else "—", cls="stat-value"),
            cls="stat-item"),
        cls="integration-stats",
        style="margin-bottom:1.2rem; padding:.6rem .8rem; background:var(--bg-raise); border-radius:.5rem;",
    )

    # Pipedrive section
    pipedrive_section = Details(
        Summary(
            H3(
                Span("⇄", style="margin-right:.4rem;"),
                "Pipedrive CRM",
                Span("connected" if pd_connected else "not configured",
                     cls="mono",
                     style=f"margin-left:.6rem; font-size:.68rem; color:{'var(--accent)' if pd_connected else 'var(--ink-dim)'};"),
            ),
        ),
        _build_pipedrive_section(uid, pd_connected, pd_domain, sync_stats,
                                 companies, lps, sequences, sym),
        open=True,
        cls="integration-top-section",
    )

    # Data Sources section
    source_cards = [_build_data_source_card(src, country_stats, sym) for src in DATA_SOURCES]

    data_sources_section = Details(
        Summary(
            H3(
                Span("◈", style="margin-right:.4rem;"),
                "Data Sources",
                Span(f"{active_sources}/{len(DATA_SOURCES)} active",
                     cls="mono",
                     style="margin-left:.6rem; font-size:.68rem; color:var(--ink-dim);"),
            ),
        ),
        Div(*source_cards),
        open=True,
        cls="integration-top-section",
    )

    body = Body(
        signin_overlay(lang=lang),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="",
                  current_currency=get_currency(sess),
                  current_path="/app/integrations", lang=lang),
        Div(
            Div(
                Div(
                    Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    Span("Integrations", cls="chat-header-title"),
                    cls="chat-header-left",
                ),
                Div(copilot_toggle_btn(lang=lang), cls="chat-header-actions"),
                cls="chat-header",
            ),
            Div(
                overview_bar,
                pipedrive_section,
                data_sources_section,
                cls="companies-wrap",
                style="padding: 1rem 1.5rem;",
            ),
            cls="center-pane pipeline-center",
        ),
        copilot_pane(
            page_name="Integrations",
            page_context={
                "page": "Integrations",
                "pipedrive_connected": pd_connected,
                "companies_synced": sync_stats.get("company", {}).get("count", 0),
                "lps_synced": sync_stats.get("investor", {}).get("count", 0),
                "total_companies": total_companies,
                "active_sources": active_sources,
            },
            lang=lang,
        ),
        Script(src=_versioned("chat.js")),
        Script(src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"),
        Script(src=_versioned("copilot.js")),
        cls="bg-bg text-ink font-sans antialiased app",
    )
    return Html(_head(), body, lang=lang)


# ── POST routes ──────────────────────────────────────────────────────

@rt("/app/integrations/connect", methods=["POST"])
async def integrations_connect(sess, api_token: str = "", domain: str = ""):
    from starlette.responses import Response

    uid, _ = _ensure_user(sess)
    api_token = api_token.strip()
    domain = domain.strip().lower().replace(".pipedrive.com", "")

    if not api_token or not domain:
        return Response(status_code=400, content="API token and domain are required",
                        headers={"HX-Reswap": "innerHTML", "HX-Retarget": "#pd-connect-error"})

    result = test_connection(api_token, domain)
    if not result:
        return Response(status_code=400, content="Invalid token or domain — could not connect",
                        headers={"HX-Reswap": "innerHTML", "HX-Retarget": "#pd-connect-error"})

    save_user_token(uid, api_token, domain)
    return Response(status_code=200, headers={"HX-Redirect": "/app/integrations"})


@rt("/app/integrations/disconnect", methods=["POST"])
async def integrations_disconnect(sess):
    from starlette.responses import Response
    uid, _ = _ensure_user(sess)
    delete_user_token(uid)
    return Response(status_code=200, headers={"HX-Redirect": "/app/integrations"})


@rt("/app/integrations/sync", methods=["POST"])
async def integrations_sync(sess, target: str = "companies"):
    import threading
    uid, _ = _ensure_user(sess)

    def _run_sync():
        import logging
        from tools.pipedrive import set_user_pipedrive
        logging.basicConfig(level=logging.INFO)
        set_user_pipedrive(uid)
        if target == "setup":
            from tools.pipedrive import ensure_pipelines
            ensure_pipelines()
        elif target == "lps":
            from scripts.sync_pipedrive import push_lps
            push_lps()
        else:
            from scripts.sync_pipedrive import push_companies
            push_companies()

    t = threading.Thread(target=_run_sync, daemon=True)
    t.start()

    from starlette.responses import Response
    return Response(status_code=200, headers={"HX-Redirect": "/app/integrations"})
