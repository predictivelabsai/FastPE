"""Portfolio Management — simulated PE portfolio of Baltic companies.

Three sub-pages behind a tab bar:

  /app/portfolio              → Dashboard (KPI cards, value bridge, health donut, top holdings)
  /app/portfolio/analytics    → Analytics (bubble chart, heatmap, sector allocation)
  /app/portfolio/kpis         → KPI Scorecard (EBITDA/revenue trend lines, margin targets)

Picks the top companies by revenue as a simulated "held" portfolio. All
Plotly charts rendered server-side (plotly.js CDN in <head>).
"""

from __future__ import annotations

import plotly.graph_objects as go

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Div, Span, H2, H3, P, A, Button, Table, Thead, Tbody, Tr, Th, Td, Dl, Dt, Dd,
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
PLOTLY_HEAD = Script(src="https://cdn.plot.ly/plotly-2.35.2.min.js")

PORTFOLIO_SIZE = 15

TABS = [
    ("Dashboard",  "/app/portfolio"),
    ("Analytics",  "/app/portfolio/analytics"),
    ("KPIs",       "/app/portfolio/kpis"),
]


# ── Shared helpers ──────────────────────────────────────────────────────────

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


def _tab_bar(active_path: str):
    items = []
    for label, href in TABS:
        cls = "port-tab active" if href == active_path else "port-tab"
        items.append(A(label, href=href, cls=cls))
    return Div(*items, cls="port-tabs")


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
    return fetch_all(f"""
        SELECT id, slug, name, country, sector, sub_sector, hq_city,
               revenue_ltm, ebitda_ltm, ebitda_margin, employees,
               enterprise_value, growth_rate, founded_year
        FROM pehero.companies
        WHERE revenue_ltm IS NOT NULL AND ebitda_ltm IS NOT NULL
        ORDER BY revenue_ltm DESC
        LIMIT {PORTFOLIO_SIZE}
    """)


def _page_shell(sess, active_path: str, body_content, copilot_page: str = "Portfolio"):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)
    companies = _get_portfolio()

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
                Div(copilot_toggle_btn(lang=lang), cls="chat-header-actions"),
                cls="chat-header",
            ),
            _tab_bar(active_path),
            Div(body_content, cls="companies-wrap"),
            cls="center-pane pipeline-center",
        ),
        copilot_pane(
            page_name=copilot_page,
            page_context={"page": "Portfolio Management", "portfolio_size": len(companies)},
            lang=lang,
        ),
        Script(src=_versioned("chat.js")),
        Script(src=_versioned("copilot.js")),
        cls="bg-bg text-ink font-sans antialiased app pipeline-app",
    )
    return Html(_head(t("port_title", lang)), body, lang=lang)


# ── Charts ──────────────────────────────────────────────────────────────────

def _value_bridge_fig(companies):
    """EBITDA waterfall: entry value → sector contributions → current total."""
    if not companies:
        return None
    sec_map: dict[str, float] = {}
    for c in companies:
        sec = (c.get("sector") or "Other").replace("_", " ").title()
        sec_map[sec] = sec_map.get(sec, 0) + float(c.get("ebitda_ltm") or 0)
    sorted_secs = sorted(sec_map.items(), key=lambda kv: -kv[1])
    total = sum(v for _, v in sorted_secs)

    labels = ["Entry EBITDA"] + [s for s, _ in sorted_secs] + ["Current"]
    amounts = [0.0] + [v / 1e6 for _, v in sorted_secs] + [total / 1e6]
    measure = ["absolute"] + ["relative"] * len(sorted_secs) + ["total"]

    fig = go.Figure(go.Waterfall(
        orientation="v", measure=measure, x=labels, y=amounts,
        text=[f"{a:+.1f}" if m == "relative" else f"{a:.1f}" for a, m in zip(amounts, measure)],
        textposition="outside",
        connector=dict(line=dict(color="#cfcfd6")),
        increasing=dict(marker=dict(color="#1F5D43")),
        decreasing=dict(marker=dict(color="#c0392b")),
        totals=dict(marker=dict(color="#C89B5B")),
    ))
    fig.update_layout(yaxis_title="EBITDA (€M)")
    return _fig(fig, height=360)


def _health_donut(companies):
    """Portfolio health donut: green (margin>20%), amber (10-20%), red (<10%)."""
    g = sum(1 for c in companies if float(c.get("ebitda_margin") or 0) > 20)
    a = sum(1 for c in companies if 10 <= float(c.get("ebitda_margin") or 0) <= 20)
    r = sum(1 for c in companies if float(c.get("ebitda_margin") or 0) < 10)
    if g + a + r == 0:
        return None
    fig = go.Figure(go.Pie(
        labels=["Healthy (>20%)", "Watch (10-20%)", "At risk (<10%)"],
        values=[g, a, r], hole=0.62,
        marker=dict(colors=["#1F5D43", "#C89B5B", "#c0392b"]),
        textinfo="value", sort=False))
    fig.update_layout(showlegend=True)
    return _fig(fig, height=300)


def _bubble_fig(companies):
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


def _kpi_trend_fig(company_ids: list[int]):
    """Yearly revenue + EBITDA trend for the portfolio (from financials table)."""
    if not company_ids:
        return None
    ids = ",".join(str(i) for i in company_ids)
    rows = fetch_all(f"""
        SELECT EXTRACT(YEAR FROM month)::int AS yr,
               SUM(revenue) AS total_rev,
               SUM(ebitda) AS total_ebitda,
               COUNT(DISTINCT company_id) AS companies
        FROM pehero.financials
        WHERE company_id IN ({ids})
        GROUP BY yr
        HAVING COUNT(DISTINCT company_id) >= 5
        ORDER BY yr
    """)
    if not rows:
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[r["yr"] for r in rows],
        y=[float(r["total_rev"]) / 1e6 for r in rows],
        mode="lines+markers", name="Revenue (€M)",
        line=dict(color="#1F5D43", width=2)))
    fig.add_trace(go.Scatter(
        x=[r["yr"] for r in rows],
        y=[float(r["total_ebitda"]) / 1e6 for r in rows],
        mode="lines+markers", name="EBITDA (€M)",
        line=dict(color="#C89B5B", width=2)))
    fig.update_layout(xaxis_title="Year", yaxis_title="€M")
    return _fig(fig, height=360)


def _margin_trend_fig(company_ids: list[int]):
    """Yearly EBITDA margin trend for the portfolio."""
    if not company_ids:
        return None
    ids = ",".join(str(i) for i in company_ids)
    rows = fetch_all(f"""
        SELECT EXTRACT(YEAR FROM month)::int AS yr,
               SUM(revenue) AS total_rev,
               SUM(ebitda) AS total_ebitda
        FROM pehero.financials
        WHERE company_id IN ({ids})
        GROUP BY yr
        HAVING SUM(revenue) > 0 AND COUNT(DISTINCT company_id) >= 5
        ORDER BY yr
    """)
    if not rows:
        return None
    fig = go.Figure()
    margins = [float(r["total_ebitda"]) / float(r["total_rev"]) * 100 for r in rows]
    fig.add_trace(go.Scatter(
        x=[r["yr"] for r in rows], y=margins,
        mode="lines+markers", name="EBITDA margin (%)",
        line=dict(color="#2b6cb0", width=2),
        fill="tozeroy", fillcolor="rgba(43,108,176,0.08)"))
    fig.add_hline(y=20, line_dash="dash", line_color="#B57D3E",
                  annotation_text="Target: 20%", annotation_position="top left")
    fig.update_layout(xaxis_title="Year", yaxis_title="Margin (%)")
    return _fig(fig, height=320)


def _growth_trend_fig(company_ids: list[int]):
    """Year-over-year revenue growth rate for the portfolio."""
    if not company_ids:
        return None
    ids = ",".join(str(i) for i in company_ids)
    rows = fetch_all(f"""
        SELECT EXTRACT(YEAR FROM month)::int AS yr,
               SUM(revenue) AS total_rev
        FROM pehero.financials
        WHERE company_id IN ({ids})
        GROUP BY yr
        HAVING COUNT(DISTINCT company_id) >= 5
        ORDER BY yr
    """)
    if len(rows) < 2:
        return None
    years, growths = [], []
    for i in range(1, len(rows)):
        prev = float(rows[i - 1]["total_rev"])
        curr = float(rows[i]["total_rev"])
        if prev > 0:
            years.append(rows[i]["yr"])
            growths.append((curr - prev) / prev * 100)
    fig = go.Figure()
    colors = ["#1F5D43" if g >= 0 else "#c0392b" for g in growths]
    fig.add_trace(go.Bar(
        x=years, y=growths,
        marker_color=colors,
        text=[f"{g:+.1f}%" for g in growths],
        textposition="outside"))
    fig.update_layout(xaxis_title="Year", yaxis_title="YoY growth (%)")
    return _fig(fig, height=320)


# ── Tab 1: Dashboard ────────────────────────────────────────────────────────

@rt("/app/portfolio")
def portfolio_home(sess):
    companies = _get_portfolio()

    if not companies:
        return _page_shell(sess, "/app/portfolio",
                           Div(P("No portfolio companies yet.", cls="search-empty")))

    total_rev = sum(float(c["revenue_ltm"] or 0) for c in companies)
    total_ebitda = sum(float(c["ebitda_ltm"] or 0) for c in companies)
    total_ev = sum(float(c["enterprise_value"] or 0) for c in companies)
    avg_margin = total_ebitda / total_rev * 100 if total_rev else 0
    avg_growth = sum(float(c["growth_rate"] or 0) for c in companies) / len(companies)
    total_employees = sum(int(c["employees"] or 0) for c in companies)
    n_countries = len({c["country"] for c in companies if c.get("country")})
    n_sectors = len({c["sector"] for c in companies if c.get("sector")})

    metrics = Div(
        _kpi_card("Portfolio companies", str(len(companies)),
                  f"{n_countries} countries · {n_sectors} sectors"),
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

    bridge = _value_bridge_fig(companies)
    donut = _health_donut(companies)

    # Top holdings by EV
    top = sorted(companies, key=lambda c: float(c.get("enterprise_value") or 0), reverse=True)[:8]
    top_rows = [Tr(
        Td(A(c["name"], href=f"/app/pipeline/{c['slug']}", cls="company-link")),
        Td((c.get("sector") or "").replace("_", " ").title()),
        Td(_fmt_eur(c.get("enterprise_value")), cls="text-right mono"),
        Td(_pct(c.get("ebitda_margin")), cls="text-right mono"),
        Td(_pct(c.get("growth_rate")), cls="text-right mono"),
    ) for c in top]

    content = Div(
        metrics,
        Div(H3("Value bridge — EBITDA by sector"),
            bridge or P("No data."), cls="portfolio-card"),
        Div(
            Div(H3("Portfolio health"),
                donut or P("No data."), cls="portfolio-card"),
            Div(H3("Top holdings by enterprise value"),
                Table(
                    Thead(Tr(Th("Company"), Th("Sector"),
                             Th("EV", cls="text-right"), Th("Margin", cls="text-right"),
                             Th("Growth", cls="text-right"))),
                    Tbody(*top_rows),
                    cls="search-table",
                ), cls="portfolio-card"),
            cls="portfolio-grid2",
        ),
    )
    return _page_shell(sess, "/app/portfolio", content, "Portfolio")


# ── Tab 2: Analytics ────────────────────────────────────────────────────────

@rt("/app/portfolio/analytics")
def portfolio_analytics(sess):
    companies = _get_portfolio()

    if not companies:
        return _page_shell(sess, "/app/portfolio/analytics",
                           Div(P("No portfolio companies yet.", cls="search-empty")),
                           "Portfolio Analytics")

    bubble = _bubble_fig(companies)
    heat = _heatmap_fig(companies)

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

    content = Div(
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
    return _page_shell(sess, "/app/portfolio/analytics", content, "Portfolio Analytics")


# ── Tab 3: KPI Scorecard ───────────────────────────────────────────────────

@rt("/app/portfolio/kpis")
def portfolio_kpis(sess):
    companies = _get_portfolio()

    if not companies:
        return _page_shell(sess, "/app/portfolio/kpis",
                           Div(P("No portfolio companies yet.", cls="search-empty")),
                           "Portfolio KPIs")

    company_ids = [c["id"] for c in companies]

    rev_ebitda = _kpi_trend_fig(company_ids)
    margin = _margin_trend_fig(company_ids)
    growth = _growth_trend_fig(company_ids)

    # Per-company KPI table: current metrics vs targets
    kpi_rows = []
    for c in companies:
        margin_val = float(c.get("ebitda_margin") or 0)
        target = 20.0
        delta = margin_val - target
        delta_style = f"color:{'#1F5D43' if delta >= 0 else '#c0392b'}"
        kpi_rows.append(Tr(
            Td(A(c["name"], href=f"/app/pipeline/{c['slug']}", cls="company-link")),
            Td(c["country"] or "—"),
            Td(_fmt_eur(c["revenue_ltm"]), cls="text-right mono"),
            Td(_fmt_eur(c["ebitda_ltm"]), cls="text-right mono"),
            Td(_pct(c.get("ebitda_margin")), cls="text-right mono"),
            Td(f"20.0%", cls="text-right mono", style="color:#7a7a85"),
            Td(f"{delta:+.1f}pp", cls="text-right mono", style=delta_style),
        ))

    content = Div(
        Div(H3("Portfolio revenue & EBITDA (annual, €M)"),
            rev_ebitda or P("No financial history."), cls="portfolio-card"),
        Div(
            Div(H3("EBITDA margin vs. target"),
                margin or P("No data."), cls="portfolio-card"),
            Div(H3("Year-over-year revenue growth"),
                growth or P("No data."), cls="portfolio-card"),
            cls="portfolio-grid2",
        ),
        H3("Company scorecard — margin vs. target", cls="section-title"),
        Table(
            Thead(Tr(
                Th("Company"), Th("Country"),
                Th("Revenue", cls="text-right"), Th("EBITDA", cls="text-right"),
                Th("Margin", cls="text-right"), Th("Target", cls="text-right"),
                Th("Delta", cls="text-right"),
            )),
            Tbody(*kpi_rows),
            cls="search-table",
        ),
    )
    return _page_shell(sess, "/app/portfolio/kpis", content, "Portfolio KPIs")
