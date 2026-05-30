"""Valuation Simulator — interactive company valuation with 3 methods.

/app/valuation           → simulator page
GET /app/valuation/data  → JSON company financials for JS
"""

from __future__ import annotations

import json

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Div, Span, H2, H3, H4, P, A, Button, Form, Input, Select, Option, Label,
    Table, Thead, Tbody, Tr, Th, Td,
)
from starlette.requests import Request
from starlette.responses import JSONResponse

from app import rt
from chat.components import left_pane, signin_overlay
from chat.layout import _versioned
from utils.session import get_currency, currency_symbol
from utils.i18n import t, get_lang
from chat.routes import _ensure_user, _list_sessions
from db import fetch_all, fetch_one
from landing.components import TAILWIND_CONFIG, _favicon_links


SECTOR_MULTIPLES = {
    "healthcare":         {"ev_revenue": 2.5, "ev_ebitda": 12.0},
    "software":           {"ev_revenue": 4.0, "ev_ebitda": 18.0},
    "industrials":        {"ev_revenue": 1.2, "ev_ebitda": 8.0},
    "financial_services": {"ev_revenue": 3.0, "ev_ebitda": 10.0},
    "business_services":  {"ev_revenue": 1.8, "ev_ebitda": 9.0},
    "consumer":           {"ev_revenue": 1.5, "ev_ebitda": 8.5},
}


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
        Script(src="https://cdn.tailwindcss.com"),
        Script(NotStr(TAILWIND_CONFIG)),
        Link(rel="stylesheet", href="/static/site.css"),
        Link(rel="stylesheet", href=_versioned("app.css")),
        Link(rel="stylesheet", href="/static/pipeline.css"),
    )


@rt("/app/valuation")
def valuation_home(sess, company: str = ""):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)
    sym = currency_symbol(get_currency(sess))

    companies = fetch_all(
        "SELECT slug, name, sector, revenue_ltm, ebitda_ltm, ebitda_margin, growth_rate "
        "FROM pehero.companies WHERE revenue_ltm > 0 ORDER BY name LIMIT 200"
    )

    selected = None
    if company:
        selected = fetch_one(
            "SELECT slug, name, sector, sub_sector, revenue_ltm, ebitda_ltm, "
            "ebitda_margin, growth_rate, employees, hq_city, country "
            "FROM pehero.companies WHERE slug = %s", (company,)
        )

    # Sector multiples as JSON for JS
    multiples_json = json.dumps(SECTOR_MULTIPLES)

    # Company selector
    selector = Form(
        Select(
            Option(t("val_select_company", lang), value=""),
            *[Option(
                f"{c['name'][:35]} — {sym}{(c['revenue_ltm'] or 0)/1e6:.1f}M",
                value=c["slug"],
                selected=c["slug"] == company,
            ) for c in companies],
            name="company", cls="val-company-select",
            onchange="this.form.submit()",
        ),
        method="get", action="/app/valuation",
    )

    # Company summary card (if selected)
    summary = Div(cls="val-summary", id="val-summary")
    if selected:
        rev = selected["revenue_ltm"] or 0
        ebitda = selected["ebitda_ltm"] or 0
        margin = selected["ebitda_margin"] or 0
        growth = selected["growth_rate"] or 0
        sector = selected["sector"] or "healthcare"
        sm = SECTOR_MULTIPLES.get(sector, {"ev_revenue": 2.0, "ev_ebitda": 10.0})

        summary = Div(
            Div(
                H3(selected["name"], cls="val-company-name"),
                Span(f"{selected.get('hq_city', '')} · {(selected.get('sector', '')).replace('_', ' ').title()}",
                     cls="val-company-meta"),
                cls="val-company-header",
            ),
            Div(
                _metric_card(t("val_revenue", lang), f"{sym}{rev/1e6:.2f}M"),
                _metric_card(t("val_ebitda", lang), f"{sym}{ebitda/1e6:.2f}M"),
                _metric_card(t("val_margin", lang), f"{margin:.1f}%"),
                _metric_card(t("val_growth", lang), f"{growth:+.1f}%"),
                cls="val-metrics",
            ),
            cls="val-summary",
            id="val-summary",
        )

    # Simulator panel (3 methods)
    simulator = Div(cls="val-simulator", id="val-simulator")
    if selected:
        rev = float(selected["revenue_ltm"] or 0)
        ebitda = float(selected["ebitda_ltm"] or 0)
        growth = float(selected["growth_rate"] or 0)

        simulator = Div(
            # Method 1: Revenue Multiple
            Div(
                H4(t("val_method_rev", lang), cls="val-method-title"),
                Div(
                    _slider("rev_multiple", t("val_rev_multiple", lang), sm["ev_revenue"], 0.5, 10.0, 0.1),
                    cls="val-inputs",
                ),
                Div(
                    Span(t("val_ev", lang), cls="val-result-label"),
                    Span(id="rev-ev", cls="val-result-value"),
                    cls="val-result",
                ),
                cls="val-method",
            ),
            # Method 2: EBITDA Multiple
            Div(
                H4(t("val_method_ebitda", lang), cls="val-method-title"),
                Div(
                    _slider("ebitda_multiple", t("val_ebitda_multiple", lang), sm["ev_ebitda"], 3.0, 30.0, 0.5),
                    cls="val-inputs",
                ),
                Div(
                    Span(t("val_ev", lang), cls="val-result-label"),
                    Span(id="ebitda-ev", cls="val-result-value"),
                    cls="val-result",
                ),
                cls="val-method",
            ),
            # Method 3: DCF
            Div(
                H4(t("val_method_dcf", lang), cls="val-method-title"),
                Div(
                    _slider("dcf_growth", t("val_dcf_growth", lang), max(growth, 5.0), 0.0, 30.0, 0.5),
                    _slider("dcf_discount", t("val_dcf_discount", lang), 12.0, 5.0, 25.0, 0.5),
                    _slider("dcf_terminal", t("val_dcf_terminal", lang), 3.0, 1.0, 8.0, 0.5),
                    _slider("dcf_years", t("val_dcf_years", lang), 5, 3, 10, 1),
                    cls="val-inputs",
                ),
                Div(
                    Span(t("val_ev", lang), cls="val-result-label"),
                    Span(id="dcf-ev", cls="val-result-value"),
                    cls="val-result",
                ),
                cls="val-method",
            ),
            # Comparison bar
            Div(
                H4(t("val_comparison", lang), cls="val-method-title"),
                Div(id="val-comparison-bars", cls="val-bars"),
                cls="val-method val-comparison-section",
            ),
            cls="val-simulator",
            id="val-simulator",
        )

    # Inline JS for live simulation
    sim_js = ""
    if selected:
        sim_js = f"""
<script>
(function() {{
    const SYM = "{sym}";
    const REV = {rev};
    const EBITDA = {ebitda};

    function fmt(v) {{
        if (v >= 1e9) return SYM + (v/1e9).toFixed(2) + "B";
        if (v >= 1e6) return SYM + (v/1e6).toFixed(2) + "M";
        if (v >= 1e3) return SYM + (v/1e3).toFixed(0) + "K";
        return SYM + v.toFixed(0);
    }}

    function calc() {{
        // Revenue multiple
        var rm = parseFloat(document.getElementById("rev_multiple").value);
        document.getElementById("rev_multiple_val").textContent = rm.toFixed(1) + "x";
        var revEV = REV * rm;
        document.getElementById("rev-ev").textContent = fmt(revEV);

        // EBITDA multiple
        var em = parseFloat(document.getElementById("ebitda_multiple").value);
        document.getElementById("ebitda_multiple_val").textContent = em.toFixed(1) + "x";
        var ebitdaEV = EBITDA * em;
        document.getElementById("ebitda-ev").textContent = fmt(ebitdaEV);

        // DCF
        var g = parseFloat(document.getElementById("dcf_growth").value) / 100;
        var d = parseFloat(document.getElementById("dcf_discount").value) / 100;
        var tg = parseFloat(document.getElementById("dcf_terminal").value) / 100;
        var n = parseInt(document.getElementById("dcf_years").value);
        document.getElementById("dcf_growth_val").textContent = (g*100).toFixed(1) + "%";
        document.getElementById("dcf_discount_val").textContent = (d*100).toFixed(1) + "%";
        document.getElementById("dcf_terminal_val").textContent = (tg*100).toFixed(1) + "%";
        document.getElementById("dcf_years_val").textContent = n + "yr";

        var fcf = EBITDA > 0 ? EBITDA * 0.7 : REV * 0.08;
        var pv = 0;
        for (var i = 1; i <= n; i++) {{
            fcf *= (1 + g);
            pv += fcf / Math.pow(1 + d, i);
        }}
        var tv = (d > tg) ? (fcf * (1 + tg)) / (d - tg) : fcf * 15;
        var pvTV = tv / Math.pow(1 + d, n);
        var dcfEV = pv + pvTV;
        document.getElementById("dcf-ev").textContent = fmt(dcfEV);

        // Comparison bars
        var maxEV = Math.max(revEV, ebitdaEV, dcfEV, 1);
        var bars = document.getElementById("val-comparison-bars");
        bars.innerHTML = [
            ["Revenue Multiple", revEV, "#1F5D43"],
            ["EBITDA Multiple", ebitdaEV, "#2F7151"],
            ["DCF", dcfEV, "#4A8E66"],
        ].map(function(b) {{
            var pct = Math.round(b[1] / maxEV * 100);
            return '<div class="val-bar-row">' +
                '<span class="val-bar-label">' + b[0] + '</span>' +
                '<div class="val-bar-track"><div class="val-bar-fill" style="width:' + pct + '%;background:' + b[2] + '"></div></div>' +
                '<span class="val-bar-value">' + fmt(b[1]) + '</span></div>';
        }}).join("");
    }}

    document.querySelectorAll(".val-slider").forEach(function(s) {{
        s.addEventListener("input", calc);
    }});
    calc();
}})();
</script>"""

    body = Body(
        signin_overlay(lang=lang),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="",
                  current_currency=get_currency(sess),
                  current_path="/app/valuation", lang=lang),
        Div(
            Div(
                Div(
                    Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    Span(t("val_title", lang), cls="chat-header-title"),
                    cls="chat-header-left",
                ),
                Div(
                    A(t("chat_back", lang), href="/app", cls="back-to-chat-btn"),
                    cls="chat-header-actions",
                ),
                cls="chat-header",
            ),
            Div(
                selector,
                summary,
                simulator,
                cls="companies-wrap",
            ),
            cls="center-pane pipeline-center",
        ),
        Script(src=_versioned("chat.js")),
        NotStr(sim_js),
        cls="bg-bg text-ink font-sans antialiased app pane-closed pipeline-app",
    )
    return Html(_head(t("val_title", lang)), body, lang=lang)


def _metric_card(label: str, value: str):
    return Div(
        Span(label, cls="val-metric-label"),
        Span(value, cls="val-metric-value"),
        cls="val-metric-card",
    )


def _slider(id: str, label: str, default, min_val, max_val, step):
    return Div(
        Div(
            Label(label, cls="val-slider-label"),
            Span(str(default), id=f"{id}_val", cls="val-slider-val"),
            cls="val-slider-header",
        ),
        Input(type="range", id=id, name=id, cls="val-slider",
              min=str(min_val), max=str(max_val), step=str(step),
              value=str(default)),
        cls="val-slider-group",
    )
