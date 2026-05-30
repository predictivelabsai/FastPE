"""Integrations page — Pipedrive CRM dashboard with sync status, deal table, actions.

/app/integrations                → main dashboard
/app/integrations/sync           → trigger sync (POST)
/app/integrations/pipedrive      → Pipedrive deal table
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Div, Span, H2, H3, H4, P, A, Button, Form, Input, Select, Option,
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


@rt("/app/integrations")
def integrations_home(sess):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)
    sym = currency_symbol(get_currency(sess))

    pd_connected = bool(settings().pipedrive_api_token)

    # Sync stats
    sync_rows = fetch_all(
        "SELECT entity_type, count(*) as n, max(last_synced) as last_sync "
        "FROM pehero.pipedrive_sync GROUP BY entity_type ORDER BY entity_type"
    ) if pd_connected or True else []

    sync_stats = {}
    for r in sync_rows:
        sync_stats[r["entity_type"]] = {"count": r["n"], "last_sync": r["last_sync"]}

    # Companies with sync status
    companies = fetch_all(
        "SELECT c.id, c.slug, c.name, c.country, c.sector, c.revenue_ltm, "
        "c.ebitda_ltm, c.deal_stage, c.hq_city, "
        "ps.pipedrive_id, ps.last_synced "
        "FROM pehero.companies c "
        "LEFT JOIN pehero.pipedrive_sync ps ON ps.entity_type = 'company' AND ps.pehero_id = c.id "
        "WHERE c.deal_stage IS NOT NULL "
        "ORDER BY c.revenue_ltm DESC NULLS LAST LIMIT 100"
    )

    # LP sync status
    lps = fetch_all(
        "SELECT i.id, i.name, i.firm, i.lp_type, i.stage, i.commitment_size, "
        "i.last_touch, ps.pipedrive_id, ps.last_synced "
        "FROM pehero.investor_crm i "
        "LEFT JOIN pehero.pipedrive_sync ps ON ps.entity_type = 'investor' AND ps.pehero_id = i.id "
        "ORDER BY i.commitment_size DESC NULLS LAST LIMIT 50"
    )

    # Outreach sequences
    sequences = fetch_all(
        "SELECT os.id, os.sequence_type, os.status, os.created_at, os.touches, "
        "c.name as company_name, i.name as investor_name "
        "FROM pehero.outreach_sequences os "
        "LEFT JOIN pehero.companies c ON c.id = os.company_id "
        "LEFT JOIN pehero.investor_crm i ON i.id = os.investor_id "
        "ORDER BY os.created_at DESC LIMIT 20"
    )

    # Status card
    status_card = Div(
        Div(
            H3("Pipedrive CRM"),
            _status_badge(pd_connected),
            cls="integration-status-header",
        ),
        Div(
            Div(
                Span("Domain", cls="stat-label"),
                Span(settings().pipedrive_domain or "not set", cls="stat-value mono"),
                cls="stat-item",
            ),
            Div(
                Span("Companies synced", cls="stat-label"),
                Span(str(sync_stats.get("company", {}).get("count", 0)), cls="stat-value"),
                cls="stat-item",
            ),
            Div(
                Span("LPs synced", cls="stat-label"),
                Span(str(sync_stats.get("investor", {}).get("count", 0)), cls="stat-value"),
                cls="stat-item",
            ),
            Div(
                Span("Last sync", cls="stat-label"),
                Span(
                    _time_ago(sync_stats.get("company", {}).get("last_sync"))
                    if sync_stats.get("company") else "never",
                    cls="stat-value",
                ),
                cls="stat-item",
            ),
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
            cls="integration-actions",
        ),
        cls="integration-card",
    )

    # Deal sourcing table
    deal_table = Details(
        Summary(H4(f"Deal Sourcing Pipeline · {len(companies)} companies")),
        Table(
            Thead(Tr(
                Th("Company"),
                Th("Country"),
                Th("Sector"),
                Th("Revenue", cls="text-right"),
                Th("Stage"),
                Th("Pipedrive"),
                Th("Last sync"),
            )),
            Tbody(
                *[Tr(
                    Td(A(c["name"][:35], href=f"/app/pipeline/{c['slug']}", cls="company-link")),
                    Td(c["country"] or "—"),
                    Td(Span((c["sector"] or "").replace("_", " ").title(), cls="sector-chip")),
                    Td(_fmt_revenue(c["revenue_ltm"], sym), cls="text-right mono"),
                    Td(_stage_badge(c["deal_stage"])),
                    Td(
                        Span(f"#{c['pipedrive_id']}", cls="mono pd-id")
                        if c["pipedrive_id"]
                        else Span("—", cls="text-muted")
                    ),
                    Td(_time_ago(c["last_synced"]) if c["last_synced"] else "—"),
                    cls="search-row",
                ) for c in companies],
            ),
            cls="search-table",
        ),
        open=True,
        cls="integration-section",
    )

    # LP table
    lp_table = Details(
        Summary(H4(f"LP Fundraising · {len(lps)} investors")),
        Table(
            Thead(Tr(
                Th("Name"),
                Th("Firm"),
                Th("Type"),
                Th("Commitment", cls="text-right"),
                Th("Stage"),
                Th("Pipedrive"),
                Th("Last touch"),
            )),
            Tbody(
                *[Tr(
                    Td(lp["name"][:30]),
                    Td((lp["firm"] or "—")[:25]),
                    Td(Span((lp["lp_type"] or "").replace("_", " ").title(), cls="sector-chip")),
                    Td(_fmt_revenue(lp["commitment_size"], sym), cls="text-right mono"),
                    Td(_stage_badge(lp["stage"])),
                    Td(
                        Span(f"#{lp['pipedrive_id']}", cls="mono pd-id")
                        if lp["pipedrive_id"]
                        else Span("—", cls="text-muted")
                    ),
                    Td(str(lp["last_touch"]) if lp["last_touch"] else "—"),
                    cls="search-row",
                ) for lp in lps],
            ),
            cls="search-table",
        ),
        open=False,
        cls="integration-section",
    )

    # Outreach sequences
    seq_items = []
    for s in sequences:
        target = s.get("company_name") or s.get("investor_name") or "Unknown"
        touches = s.get("touches") or []
        if isinstance(touches, str):
            try:
                touches = json.loads(touches)
            except Exception:
                touches = []
        sent = sum(1 for t in touches if t.get("sent"))
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
            Thead(Tr(
                Th("Target"),
                Th("Type"),
                Th("Status"),
                Th("Progress"),
                Th("Created"),
            )),
            Tbody(*seq_items) if seq_items else Tbody(
                Tr(Td("No sequences yet. Use the Outreach Sequencer agent to create one.",
                       colspan="5", cls="text-muted",
                       style="text-align:center; padding:2rem;")),
            ),
            cls="search-table",
        ),
        open=False,
        cls="integration-section",
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
                Div(
                    copilot_toggle_btn(lang=lang),
                    cls="chat-header-actions",
                ),
                cls="chat-header",
            ),
            Div(
                status_card,
                deal_table,
                lp_table,
                seq_table,
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
            },
            lang=lang,
        ),
        Script(src=_versioned("chat.js")),
        Script(src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"),
        Script(src=_versioned("copilot.js")),
        cls="bg-bg text-ink font-sans antialiased app",
    )
    return Html(_head(), body, lang=lang)


@rt("/app/integrations/sync", methods=["POST"])
async def integrations_sync(sess, target: str = "companies"):
    """Trigger Pipedrive sync from the UI."""
    import threading

    def _run_sync():
        import logging
        logging.basicConfig(level=logging.INFO)
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
    return Response(
        status_code=200,
        headers={"HX-Redirect": "/app/integrations"},
    )
