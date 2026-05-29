"""Pipeline kanban view — companies grouped by deal_stage.

/app/pipeline          → kanban board
/app/pipeline/<slug>   → deal detail: left brief, center chat, right artifact
"""

from __future__ import annotations

import json
from typing import Optional

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Nav, Main, Footer, Section, Article, Div, Span, A, H1, H2, H3, H4, P, Ul, Li,
    Button, Form, Textarea, Input,
)

from app import rt
from agents.registry import AGENTS, AGENTS_BY_SLUG
from chat.components import (
    left_pane, right_pane, signin_overlay, sample_cards, message_bubble,
)
from chat.layout import _versioned
from utils.session import get_currency, currency_symbol
from utils.i18n import t, get_lang
from chat.routes import _ensure_user, _list_sessions, _ensure_session, _session_messages
from db import connect, fetch_all, fetch_one
from landing.components import TAILWIND_CONFIG, _favicon_links


# Stage ordering — mirrors companies.deal_stage (pehero/schema.sql)
STAGES = [
    ("sourced",    "Sourced"),
    ("screened",   "Screened"),
    ("loi",        "LOI / IOI"),
    ("diligence",  "Diligence"),
    ("ic",         "IC"),
    ("signed",     "Signed"),
    ("closed",     "Closed"),
    ("held",       "Held"),
    ("exited",     "Exited"),
    ("passed",     "Passed"),
]

STAGE_COLORS = {
    "sourced":   "#9CA89E",
    "screened":  "#7A9E88",
    "loi":       "#C89B5B",
    "diligence": "#B57D3E",
    "ic":        "#4A8E66",
    "signed":    "#2F7151",
    "closed":    "#1F5D43",
    "held":      "#3C5748",
    "exited":    "#6B4E2F",
    "passed":    "#9C8F7A",
}


def _pipeline_head(title: str):
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


def _card_for(company: dict, sym: str = "€") -> Div:
    name = company["name"]
    sector = company.get("sector") or ""
    sub_sector = company.get("sub_sector") or ""
    rev = company.get("revenue_ltm") or 0
    eb = company.get("ebitda_ltm") or 0
    ev = company.get("enterprise_value") or 0
    mult = company.get("ask_multiple")
    intent = company.get("seller_intent") or ""

    # Heat dot for seller intent
    heat_colors = {"hot": "#B83A3A", "warm": "#C89B5B", "cold": "#7A9E88"}
    heat = heat_colors.get(intent, "#CFC8B4")

    return A(
        Div(
            Div(
                Span(cls="heat-dot", style=f"background:{heat}"),
                Span(name, cls="card-title"),
                cls="card-head",
            ),
            Div(
                Span(sub_sector or sector.replace("_", " ").title(),
                     cls="card-sub"),
                cls="card-meta",
            ),
            Div(
                Span(f"{sym}{float(rev)/1_000_000:.0f}M rev", cls="card-metric"),
                Span("·"),
                Span(f"{sym}{float(eb)/1_000_000:.1f}M EBITDA", cls="card-metric"),
                cls="card-metrics-line",
            ),
            Div(
                Span(f"EV {sym}{float(ev)/1_000_000:.0f}M" if ev else "—", cls="card-ev"),
                Span(f"{float(mult):.1f}x" if mult else "", cls="card-mult"),
                cls="card-ev-line",
            ),
            cls="deal-card",
        ),
        href=f"/app/pipeline/{company['slug']}",
        cls="deal-card-link",
    )


def _board(companies_by_stage: dict[str, list[dict]], sym: str = "€") -> Div:
    columns = []
    for stage_key, stage_label in STAGES:
        cards = companies_by_stage.get(stage_key, [])
        columns.append(Div(
            Div(
                Span(stage_label, cls="col-title"),
                Span(str(len(cards)), cls="col-count"),
                cls="col-head",
                style=f"border-bottom-color:{STAGE_COLORS.get(stage_key, '#CFC8B4')}",
            ),
            Div(*[_card_for(c, sym) for c in cards], cls="col-body"),
            cls="kanban-col",
        ))
    return Div(*columns, cls="kanban-board")


@rt("/app/pipeline")
def pipeline_home(sess, sector: str = "", ownership: str = ""):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)

    sql = ["SELECT * FROM pehero.companies WHERE TRUE"]
    params: list = []
    if sector:
        sql.append("AND sector = %s"); params.append(sector)
    if ownership:
        sql.append("AND ownership = %s"); params.append(ownership)
    sql.append("ORDER BY deal_stage, name")
    rows = fetch_all(" ".join(sql), tuple(params))

    by_stage: dict[str, list[dict]] = {}
    for r in rows:
        by_stage.setdefault(r["deal_stage"] or "sourced", []).append(r)

    sectors = sorted({r["sector"] for r in rows if r["sector"]})

    filters = Div(
        A(t("pipe_all", lang), href="/app/pipeline",
          cls=f"filter-chip{' active' if not sector and not ownership else ''}"),
        *[A(s.replace("_", " ").title(),
             href=f"/app/pipeline?sector={s}",
             cls=f"filter-chip{' active' if sector == s else ''}") for s in sectors],
        Span("·", cls="filter-divider"),
        *[A(o.replace("_", " ").title(),
             href=f"/app/pipeline?ownership={o}",
             cls=f"filter-chip{' active' if ownership == o else ''}")
          for o in ["founder", "family", "pe_backed", "vc_backed", "corporate_carve_out"]],
        cls="pipeline-filters",
    )

    body = Body(
        signin_overlay(),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="", current_currency=get_currency(sess), lang=lang),
        Div(
            Div(
                Div(
                    Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    Span(t("pipe_title", lang), cls="chat-header-title"),
                    Span("·", cls="chat-header-dot"),
                    Span(t("pipe_companies", lang).format(n=len(rows)), cls="chat-header-agent"),
                    cls="chat-header-left",
                ),
                Div(
                    A(t("chat_back", lang), href="/app", cls="back-to-chat-btn"),
                    cls="chat-header-actions",
                ),
                cls="chat-header",
            ),
            filters,
            _board(by_stage, currency_symbol(get_currency(sess))),
            cls="center-pane pipeline-center",
        ),
        Script(src=_versioned("chat.js")),
        cls="bg-bg text-ink font-sans antialiased app pane-closed pipeline-app",
    )
    return Html(_pipeline_head(t("pipe_title", lang)), body, lang=lang)


@rt("/app/pipeline/{slug}")
def deal_detail(sess, slug: str):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)

    co = fetch_one("SELECT * FROM pehero.companies WHERE slug = %s", (slug,))
    if not co:
        return Html(
            _pipeline_head("Not found"),
            Body(Div(H1("Deal not found"),
                     A("Back to pipeline", href="/app/pipeline"),
                     cls="p-10 text-ink")),
            lang="en",
        )

    cid = co["id"]

    # Pull supporting data for the deal brief (right artifact pane)
    ltm = fetch_all(
        "SELECT revenue, ebitda, adj_ebitda FROM pehero.financials "
        "WHERE company_id = %s ORDER BY month DESC LIMIT 12",
        (cid,),
    )
    ltm_rev = sum(float(r["revenue"] or 0) for r in ltm)
    ltm_eb = sum(float(r["adj_ebitda"] or r["ebitda"] or 0) for r in ltm)

    top_contracts = fetch_all(
        "SELECT counterparty, annual_value, end_date "
        "FROM pehero.contracts WHERE company_id = %s AND status = 'active' "
        "AND contract_type = 'customer_msa' ORDER BY annual_value DESC NULLS LAST LIMIT 5",
        (cid,),
    )
    findings = fetch_all(
        "SELECT agent_slug, category, severity, summary FROM pehero.dd_findings "
        "WHERE company_id = %s ORDER BY CASE severity "
        "WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 "
        "WHEN 'low' THEN 3 ELSE 4 END LIMIT 5",
        (cid,),
    )

    # Start or resume a per-deal chat session
    deal_sid_row = fetch_one(
        "SELECT id FROM pehero.chat_sessions WHERE user_id = %s AND title = %s "
        "ORDER BY updated_at DESC LIMIT 1",
        (uid or 0, f"Deal: {co['name']}"),
    ) if uid else None
    session_id = deal_sid_row["id"] if deal_sid_row else None
    messages = _session_messages(session_id) if session_id else []

    sym = currency_symbol(get_currency(sess))
    # ── Deal brief on right-side artifact pane ──
    brief_html = f"""
    <div class="deal-brief">
      <h3 class="deal-name">{co['name']}</h3>
      <div class="deal-tags">
        <span class="tag">{(co.get('sector') or '').replace('_', ' ').title()}</span>
        <span class="tag">{co.get('sub_sector') or ''}</span>
        <span class="tag tag-stage">{(co.get('deal_stage') or '').upper()}</span>
      </div>
      <div class="deal-kv">
        <div><strong>HQ</strong> {co.get('hq_city') or ''}, {co.get('hq_state') or ''} {co.get('country') or ''}</div>
        <div><strong>Employees</strong> {co.get('employees') or '—'}</div>
        <div><strong>Founded</strong> {co.get('founded_year') or '—'}</div>
        <div><strong>Ownership</strong> {(co.get('ownership') or '').replace('_', ' ')}</div>
      </div>
      <h4>LTM financials</h4>
      <div class="deal-kv">
        <div><strong>Revenue</strong> {sym}{ltm_rev/1_000_000:.1f}M</div>
        <div><strong>Adj. EBITDA</strong> {sym}{ltm_eb/1_000_000:.1f}M</div>
        <div><strong>Margin</strong> {100*ltm_eb/max(1, ltm_rev):.1f}%</div>
        <div><strong>Ask EV</strong> {sym}{float(co.get('enterprise_value') or 0)/1_000_000:.0f}M ({float(co.get('ask_multiple') or 0):.1f}x)</div>
      </div>
      <h4>Top customers</h4>
      <ul class="deal-list">
        {"".join(f"<li><span>{c['counterparty']}</span><span class='muted'>{sym}{float(c['annual_value'] or 0)/1000:.0f}k / yr</span></li>" for c in top_contracts) or "<li class='muted'>No contracts loaded.</li>"}
      </ul>
      <h4>DD findings</h4>
      <ul class="deal-list">
        {"".join(f"<li><span class='sev sev-{f['severity']}'>{f['severity']}</span><span>{f['summary']}</span></li>" for f in findings) or "<li class='muted'>No findings yet. Try running VDR Auditor.</li>"}
      </ul>
      <div class="deal-desc">{co.get('description') or ''}</div>
    </div>
    """

    # center chat bubbles if any
    bubbles = [message_bubble(m["role"], m["content"], m.get("agent_slug")) for m in messages]

    hidden_slug = Input(type="hidden", id="deal-slug", value=slug)

    body = Body(
        signin_overlay(),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid=str(session_id) if session_id else "", current_currency=get_currency(sess)),
        Div(
            Div(
                Div(
                    Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    A("← Pipeline", href="/app/pipeline", cls="back-to-chat-btn"),
                    Span("·", cls="chat-header-dot"),
                    Span(co["name"], cls="chat-header-title"),
                    Span("·", cls="chat-header-dot"),
                    Span((co.get("deal_stage") or "").upper(), cls="chat-header-agent"),
                    cls="chat-header-left",
                ),
                Div(
                    Button("Canvas", id="artifact-btn", cls="artifact-toggle-btn active",
                           onclick="toggleArtifactPane()"),
                    cls="chat-header-actions",
                ),
                cls="chat-header",
            ),
            Div(*bubbles, id="messages", cls="messages"),
            Div(
                Div(
                    P(f"Ask about {co['name']} — the deal brief is on the right. "
                      "Try 'triage this deal', 'draft IC memo', or 'summarize DD findings'.",
                      cls="text-sm"),
                    cls="deal-chat-hint",
                ) if not bubbles else Div(id="welcome-hero", style="display:none"),
                id="welcome-wrap",
            ),
            Form(
                hidden_slug,
                Textarea(
                    id="chat-input", name="msg",
                    cls="chat-textarea",
                    placeholder=f"Ask about {co['name']} — e.g. triage, LBO, DD findings",
                    rows="2",
                    onkeydown="handleKey(event)",
                    oninput="autoResize(this)",
                ),
                Button("Send", type="submit", cls="chat-send", id="send-btn"),
                id="chat-form",
                cls="chat-form",
                onsubmit="sendMessage(event)",
            ),
            sample_cards(),
            cls="center-pane",
        ),
        # Right pane pre-filled with deal brief
        Div(
            Div(
                Div(H3("Deal brief", cls="right-title"),
                    Span(co["name"], id="artifact-subtitle", cls="right-subtitle"),
                    cls="right-header-left"),
                Button("✕", cls="right-close", onclick="toggleArtifactPane()"),
                cls="right-header",
            ),
            Div(
                Div(id="artifact-empty", cls="artifact-empty", style="display:none"),
                Div(NotStr(brief_html), id="artifact-body", cls="artifact-body"),
                cls="right-body",
            ),
            id="right-pane", cls="right-pane open",
        ),
        # Prompts data for sample cards
        NotStr(f'<script id="agent-prompts-data" type="application/json">{json.dumps({a.slug: list(a.example_prompts[:6]) for a in AGENTS})}</script>'),
        NotStr(f'<script id="agent-names-data" type="application/json">{json.dumps({a.slug: a.name for a in AGENTS})}</script>'),
        Script(src=_versioned("chat.js")),
        cls="bg-bg text-ink font-sans antialiased app",
    )
    return Html(_pipeline_head(co["name"]), body, lang="en")
