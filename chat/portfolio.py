"""Portfolio Management — simulated PE portfolio of Baltic companies.

/app/portfolio   → dashboard with KPI cards, charts, and holdings table

Picks the top companies by revenue as a simulated "held" portfolio, then
renders executive-level metrics, a value vs. margin bubble chart, a
sector × country heatmap, and a holdings table — closely modeled on the
CXO Hub portfolio cockpit.
"""

from __future__ import annotations

import plotly.graph_objects as go

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Div, Span, H2, H3, P, A, Button, Table, Thead, Tbody, Tr, Th, Td,
)

from app import rt
from chat.components import left_pane, signin_overlay, copilot_pane, copilot_toggle_btn
from chat.layout import _versioned, common_scripts
from utils.session import get_currency, currency_symbol
from utils.i18n import t, get_lang
from chat.routes import _ensure_user, _list_sessions
from db import fetch_all
from landing.components import TAILWIND_CONFIG, _favicon_links

PALETTE = ["#1F5D43", "#C89B5B", "#2b6cb0", "#B57D3E", "#7A9E88", "#8a5cd1"]
PLOTLY_CDN = Script(src="https://cdn.plot.ly/plotly-2.35.2.min.js")
PLOTLY_HEAD = Script(src="https://cdn.plot.ly/plotly-2.35.2.min.js")

PORTFOLIO_SIZE = 15


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
        PLOTLY_HEAD,
    )


def _fig(fig, height=340):
    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10), height=height,
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter, -apple-system, sans-serif", size=12, color="#48484f"),
        legend=dict(orientation="h", y=-0.18),
    )
    return NotStr(fig.to_html(include_plotlyjs=False, full_html=False,
                              config={"displayModeBar": False}))


def _fmt_eur(val) -> str:
    if not val:
        return "—"
    v = float(val)
    if abs(v) >= 1_000_000:
        return f"€{v / 1_000_000:,.1f}M"
    if abs(v) >= 1_000:
        return f"€{v / 1_000:,.0f}K"
    return f"€{v:,.0f}"


def _pct(val) -> str:
    if val is None:
        return "—"
    return f"{float(val):.1f}%"


def _kpi_card(label: str, value: str, sub: str = "", accent: str = ""):
    style = f"border-left: 3px solid {accent};" if accent else ""
    return Div(
        Div(label, cls="kpi-label"),
        Div(value, cls="kpi-value"),
        Div(sub, cls="kpi-sub") if sub else "",
        cls="kpi-card", style=style,
    )


def _get_portfolio():
    """Get top companies by revenue as the simulated portfolio."""
    return fetch_all(f"""
        SELECT id, slug, name, country, sector, sub_sector, hq_city,
               revenue_ltm, ebitda_ltm, ebitda_margin, employees,
               enterprise_value, growth_rate, founded_year
        FROM pehero.companies
        WHERE revenue_ltm IS NOT NULL AND ebitda_ltm IS NOT NULL
        ORDER BY revenue_ltm DESC
        LIMIT {PORTFOLIO_SIZE}
    """)


def _bubble_fig(companies):
    """Revenue vs. EBITDA margin bubble chart (bubble size = enterprise value)."""
    pts = [c for c in companies if c.get("ebitda_margin") is not None]
    if not pts:
        return None
    sectors = sorted({c.get("sector") or "—" for c in pts})
    fig = go.Figure()
    for i, sec in enumerate(sectors):
        grp = [c for c in pts if (c.get("sector") or "—") == sec]
        fig.add_trace(go.Scatter(
            x=[float(c.get("revenue_ltm") or 0) / 1e6 for c in grp],
            y=[float(c.get("ebitda_margin") or 0) for c in grp],
            mode="markers",
            marker=dict(
                size=[max(14, min(60, float(c.get("enterprise_value") or 0) / 5e5)) for c in grp],
                color=PALETTE[i % len(PALETTE)], opacity=0.75,
                line=dict(width=1, color="#fff")),
            name=sec.replace("_", " ").title(),
            text=[f"{c['name']}<br>Revenue {_fmt_eur(c.get('revenue_ltm'))} · "
                  f"EBITDA margin {_pct(c.get('ebitda_margin'))} · "
                  f"EV {_fmt_eur(c.get('enterprise_value'))}"
                  for c in grp],
            hoverinfo="text"))
    fig.update_layout(xaxis_title="Revenue LTM (€M)", yaxis_title="EBITDA margin (%)")
    return _fig(fig, height=400)


def _heatmap_fig(companies):
    """Sector × country heatmap (count of portfolio companies)."""
    countries = sorted({c.get("country") or "—" for c in companies})
    sectors = sorted({c.get("sector") or "—" for c in companies})
    if not countries or not sectors:
        return None
    z = [[sum(1 for c in companies
              if (c.get("country") or "—") == co and (c.get("sector") or "—") == sec)
          for sec in sectors] for co in countries]
    fig = go.Figure(go.Heatmap(
        z=z, x=[s.replace("_", " ").title() for s in sectors],
        y=countries,
        colorscale=[[0, "#f0f5f2"], [1, "#1F5D43"]],
        text=z, texttemplate="%{text}", showscale=False,
        textfont=dict(size=13)))
    return _fig(fig, height=280)


def _stage_dot(stage: str) -> Span:
    colors = {
        "signed": "#4A8E66", "closed": "#2F7151", "held": "#1F5D43",
        "sourced": "#9CA89E", "screened": "#7A9E88", "diligence": "#B57D3E",
    }
    color = colors.get(stage, "#9CA89E")
    return Span("●", style=f"color:{color}; margin-right:.3rem;")


@rt("/app/portfolio")
def portfolio_home(sess):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)

    companies = _get_portfolio()

    if not companies:
        body_content = Div(P("No portfolio companies yet.", cls="search-empty"))
    else:
        # KPI metrics
        total_rev = sum(float(c["revenue_ltm"] or 0) for c in companies)
        total_ebitda = sum(float(c["ebitda_ltm"] or 0) for c in companies)
        total_ev = sum(float(c["enterprise_value"] or 0) for c in companies)
        avg_margin = total_ebitda / total_rev * 100 if total_rev else 0
        avg_growth = sum(float(c["growth_rate"] or 0) for c in companies) / len(companies)
        total_employees = sum(int(c["employees"] or 0) for c in companies)
        countries = len({c["country"] for c in companies if c.get("country")})
        sectors = len({c["sector"] for c in companies if c.get("sector")})

        metrics = Div(
            _kpi_card("Portfolio companies", str(len(companies)),
                      f"{countries} countries · {sectors} sectors"),
            _kpi_card("Total revenue", _fmt_eur(total_rev), "LTM aggregate"),
            _kpi_card("Total EBITDA", _fmt_eur(total_ebitda),
                      f"margin {avg_margin:.1f}%", accent="#1F5D43"),
            _kpi_card("Enterprise value", _fmt_eur(total_ev), "portfolio total",
                      accent="#C89B5B"),
            _kpi_card("Avg growth rate", _pct(avg_growth), accent="#2b6cb0"),
            _kpi_card("Total headcount", f"{total_employees:,}",
                      f"across {len(companies)} companies"),
            cls="portfolio-metrics",
        )

        bubble = _bubble_fig(companies)
        heat = _heatmap_fig(companies)

        # Sector capacity table
        sec_rows: dict[str, dict] = {}
        for c in companies:
            sec = (c.get("sector") or "—").replace("_", " ").title()
            d = sec_rows.setdefault(sec, {"n": 0, "ebitda": 0.0, "rev": 0.0})
            d["n"] += 1
            d["ebitda"] += float(c.get("ebitda_ltm") or 0)
            d["rev"] += float(c.get("revenue_ltm") or 0)
        cap_rows = [Tr(
            Td(sec),
            Td(str(d["n"]), cls="text-right mono"),
            Td(_fmt_eur(d["rev"]), cls="text-right mono"),
            Td(_fmt_eur(d["ebitda"]), cls="text-right mono"),
        ) for sec, d in sorted(sec_rows.items(), key=lambda kv: -kv[1]["ebitda"])]

        # Holdings table
        holding_rows = [Tr(
            Td(A(c["name"], href=f"/app/pipeline/{c['slug']}", cls="company-link")),
            Td(c["country"] or "—"),
            Td((c.get("sector") or "").replace("_", " ").title()),
            Td(_fmt_eur(c["revenue_ltm"]), cls="text-right mono"),
            Td(_fmt_eur(c["ebitda_ltm"]), cls="text-right mono"),
            Td(_pct(c.get("ebitda_margin")), cls="text-right mono"),
            Td(_fmt_eur(c.get("enterprise_value")), cls="text-right mono"),
            Td(_pct(c.get("growth_rate")), cls="text-right mono"),
        ) for c in companies]

        body_content = Div(
            metrics,
            Div(H3("Revenue vs. EBITDA margin (bubble size = enterprise value)"),
                bubble or P("No data."), cls="portfolio-card"),
            Div(
                Div(H3("Portfolio by sector × country"),
                    heat or P("No data."), cls="portfolio-card"),
                Div(H3("Sector allocation"),
                    Table(
                        Thead(Tr(Th("Sector"), Th("Companies", cls="text-right"),
                                 Th("Revenue", cls="text-right"), Th("EBITDA", cls="text-right"))),
                        Tbody(*cap_rows),
                        cls="search-table",
                    ), cls="portfolio-card"),
                cls="portfolio-grid2",
            ),
            H3("Holdings", cls="section-title"),
            Table(
                Thead(Tr(
                    Th("Company"), Th("Country"), Th("Sector"),
                    Th("Revenue", cls="text-right"), Th("EBITDA", cls="text-right"),
                    Th("Margin", cls="text-right"), Th("EV", cls="text-right"),
                    Th("Growth", cls="text-right"),
                )),
                Tbody(*holding_rows),
                cls="search-table",
            ),
        )

    body = Body(
        signin_overlay(lang=lang),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="",
                  current_currency=get_currency(sess),
                  current_path="/app/portfolio", lang=lang),
        Div(
            Div(
                Div(
                    Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    Span(t("port_title", lang), cls="chat-header-title"),
                    cls="chat-header-left",
                ),
                Div(
                    copilot_toggle_btn(lang=lang),
                    cls="chat-header-actions",
                ),
                cls="chat-header",
            ),
            Div(body_content, cls="companies-wrap"),
            cls="center-pane pipeline-center",
        ),
        copilot_pane(
            page_name="Portfolio",
            page_context={
                "page": "Portfolio Management",
                "portfolio_size": len(companies),
            },
            lang=lang,
        ),
        Script(src=_versioned("chat.js")),
        Script(src=_versioned("copilot.js")),
        cls="bg-bg text-ink font-sans antialiased app pipeline-app",
    )
    return Html(_head(t("port_title", lang)), body, lang=lang)
