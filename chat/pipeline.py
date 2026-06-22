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
    copilot_pane, copilot_toggle_btn,
)
from chat.layout import _versioned, common_scripts
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
        *common_scripts(),
        Script(src="https://cdn.tailwindcss.com"),
        Script(NotStr(TAILWIND_CONFIG)),
        Link(rel="stylesheet", href="/static/site.css"),
        Link(rel="stylesheet", href=_versioned("app.css")),
        Link(rel="stylesheet", href="/static/pipeline.css"),
    )


def _triage_badge(score, priority) -> Span:
    if score is None:
        return Span("")
    colors = {"High": "#1F5D43", "Medium": "#C89B5B", "Low": "#9CA89E"}
    bg = colors.get(priority, "#9CA89E")
    return Span(f"{float(score):.1f}", cls="triage-badge", style=f"background:{bg}")


def _card_for(company: dict, sym: str = "€") -> Div:
    name = company["name"]
    sector = company.get("sector") or ""
    sub_sector = company.get("sub_sector") or ""
    rev = company.get("revenue_ltm") or 0
    eb = company.get("ebitda_ltm") or 0
    ev = company.get("enterprise_value") or 0
    mult = company.get("ask_multiple")
    intent = company.get("seller_intent") or ""
    score = company.get("triage_score")
    priority = company.get("triage_priority")

    heat_colors = {"hot": "#B83A3A", "warm": "#C89B5B", "cold": "#7A9E88"}
    heat = heat_colors.get(intent, "#CFC8B4")

    return A(
        Div(
            Div(
                Span(cls="heat-dot", style=f"background:{heat}"),
                Span(name, cls="card-title"),
                _triage_badge(score, priority),
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


def _stage_list(rows: list[dict], stage_key: str, stage_label: str,
                 stage_total: int, page: int, total_pages: int,
                 sector: str, ownership: str, sym: str = "€") -> Div:
    """Paginated card grid for a single stage."""
    cards = [_card_for(c, sym) for c in rows]

    def _page_href(p):
        parts = {"stage": stage_key}
        if sector: parts["sector"] = sector
        if ownership: parts["ownership"] = ownership
        if p > 1: parts["page"] = str(p)
        return "/app/pipeline?" + "&".join(f"{k}={v}" for k, v in parts.items())

    pager_items = [
        A("← Back to board", href="/app/pipeline" + (f"?sector={sector}" if sector else "") + (f"{'&' if sector else '?'}ownership={ownership}" if ownership else ""),
          cls="filter-chip"),
    ]
    if page > 1:
        pager_items.append(A("‹ Prev", href=_page_href(page - 1), cls="filter-chip"))
    pager_items.append(Span(f"Page {page} of {total_pages:,} ({stage_total:,} deals)", cls="pager-info"))
    if page < total_pages:
        pager_items.append(A("Next ›", href=_page_href(page + 1), cls="filter-chip"))

    return Div(
        Div(
            Span(f"{stage_label}", cls="col-title", style=f"font-size:1.1rem;border-bottom:3px solid {STAGE_COLORS.get(stage_key, '#CFC8B4')};padding-bottom:4px"),
            cls="stage-list-header",
        ),
        Div(*cards, cls="stage-card-grid"),
        Div(*pager_items, cls="pager-bar"),
        cls="stage-list-view",
    )


def _board(companies_by_stage: dict[str, list[dict]], stage_counts: dict[str, int], sym: str = "€") -> Div:
    columns = []
    for stage_key, stage_label in STAGES:
        cards = companies_by_stage.get(stage_key, [])
        total_in_stage = stage_counts.get(stage_key, 0)
        shown = len(cards)
        overflow = total_in_stage > shown

        col_children = [_card_for(c, sym) for c in cards]
        if overflow:
            col_children.append(
                A(f"View all {total_in_stage:,}",
                  href=f"/app/pipeline?stage={stage_key}",
                  cls="col-overflow-link")
            )

        columns.append(Div(
            Div(
                Span(stage_label, cls="col-title"),
                Span(f"{total_in_stage:,}", cls="col-count"),
                cls="col-head",
                style=f"border-bottom-color:{STAGE_COLORS.get(stage_key, '#CFC8B4')}",
            ),
            Div(*col_children, cls="col-body"),
            cls="kanban-col",
        ))
    return Div(*columns, cls="kanban-board")


_CARD_COLS = (
    "slug, name, sector, sub_sector, revenue_ltm, ebitda_ltm, "
    "enterprise_value, ask_multiple, seller_intent, deal_stage, "
    "triage_score, triage_priority"
)
_CARDS_PER_STAGE = 20


_PAGE_SIZE = 50


@rt("/app/pipeline")
def pipeline_home(sess, sector: str = "", ownership: str = "", stage: str = "", page: int = 1):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)
    page = max(1, page)

    where_parts = ["TRUE"]
    params: list = []
    if sector:
        where_parts.append("sector = %s"); params.append(sector)
    if ownership:
        where_parts.append("ownership = %s"); params.append(ownership)
    where = " AND ".join(where_parts)

    counts = fetch_all(
        f"SELECT COALESCE(deal_stage, 'sourced') AS deal_stage, count(*) AS n "
        f"FROM pehero.companies WHERE {where} GROUP BY 1",
        tuple(params),
    )
    stage_counts = {r["deal_stage"]: r["n"] for r in counts}
    total = sum(stage_counts.values())

    if stage:
        stage_label = dict(STAGES).get(stage, stage.title())
        offset = (page - 1) * _PAGE_SIZE
        rows = fetch_all(
            f"SELECT {_CARD_COLS} FROM pehero.companies "
            f"WHERE {where} AND COALESCE(deal_stage, 'sourced') = %s "
            f"ORDER BY triage_score DESC NULLS LAST, enterprise_value DESC NULLS LAST, name "
            f"LIMIT {_PAGE_SIZE} OFFSET %s",
            tuple(params) + (stage, offset),
        )
        stage_total = stage_counts.get(stage, 0)
        total_pages = max(1, (stage_total + _PAGE_SIZE - 1) // _PAGE_SIZE)
        board_content = _stage_list(rows, stage, stage_label, stage_total, page, total_pages,
                                    sector, ownership, currency_symbol(get_currency(sess)))
    else:
        by_stage: dict[str, list[dict]] = {}
        for stage_key, _ in STAGES:
            if stage_counts.get(stage_key, 0) == 0:
                continue
            rows = fetch_all(
                f"SELECT {_CARD_COLS} FROM pehero.companies "
                f"WHERE {where} AND COALESCE(deal_stage, 'sourced') = %s "
                f"ORDER BY triage_score DESC NULLS LAST, enterprise_value DESC NULLS LAST, name "
                f"LIMIT {_CARDS_PER_STAGE}",
                tuple(params) + (stage_key,),
            )
            by_stage[stage_key] = rows
        board_content = _board(by_stage, stage_counts, currency_symbol(get_currency(sess)))

    sectors = sorted(
        r["sector"] for r in fetch_all(
            "SELECT DISTINCT sector FROM pehero.companies WHERE sector IS NOT NULL ORDER BY sector"
        )
    )

    def _qstr(**kw):
        parts = {k: v for k, v in {"sector": sector, "ownership": ownership, **kw}.items() if v}
        return "?" + "&".join(f"{k}={v}" for k, v in parts.items()) if parts else ""

    filters = Div(
        A(t("pipe_all", lang), href="/app/pipeline",
          cls=f"filter-chip{' active' if not sector and not ownership and not stage else ''}"),
        *[A(s.replace("_", " ").title(),
             href=f"/app/pipeline{_qstr(sector=s)}",
             cls=f"filter-chip{' active' if sector == s else ''}") for s in sectors],
        Span("·", cls="filter-divider"),
        *[A(o.replace("_", " ").title(),
             href=f"/app/pipeline{_qstr(ownership=o)}",
             cls=f"filter-chip{' active' if ownership == o else ''}")
          for o in ["founder", "family", "pe_backed", "vc_backed", "corporate_carve_out"]],
        cls="pipeline-filters",
    )

    body = Body(
        signin_overlay(),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="", current_currency=get_currency(sess), current_path="/app/pipeline", lang=lang),
        Div(
            Div(
                Div(
                    Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    Span(t("pipe_title", lang), cls="chat-header-title"),
                    Span("·", cls="chat-header-dot"),
                    Span(t("pipe_companies", lang).format(n=total), cls="chat-header-agent"),
                    cls="chat-header-left",
                ),
                Div(
                    copilot_toggle_btn(lang=lang),
                    cls="chat-header-actions",
                ),
                cls="chat-header",
            ),
            filters,
            board_content,
            cls="center-pane pipeline-center",
        ),
        copilot_pane(
            page_name="Pipeline",
            page_context={
                "page": "Pipeline",
                "total_companies": total,
                "filters": {"sector": sector, "ownership": ownership},
                "by_stage": stage_counts,
            },
            lang=lang,
        ),
        Script(src=_versioned("chat.js")),
        Script(src=_versioned("copilot.js")),
        cls="bg-bg text-ink font-sans antialiased app pipeline-app",
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
        {f'<span class="tag tag-triage tag-triage-{(co.get("triage_priority") or "").lower()}">{co.get("triage_priority")} ({float(co.get("triage_score") or 0):.1f})</span>' if co.get('triage_score') else ''}
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
        left_pane(user_email=email, sessions=sessions, current_sid=str(session_id) if session_id else "", current_currency=get_currency(sess), current_path="/app/pipeline"),
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
