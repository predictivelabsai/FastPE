"""Analytics page — natural-language → SQL over pehero.*, rendered as a Plotly chart.

/app/analytics           → text input + example prompts
POST /app/analytics/run  → returns the SQL + result table + plotly fig JSON (HTMX swap)

Uses the same Grok LLM to draft SQL against a hand-curated schema snippet, runs
it (read-only), then picks a sensible chart automatically based on result shape.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import pandas as pd
import plotly.express as px
from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Div, Span, H1, H2, H3, H4, P, A, Button, Form, Input,
)
from starlette.requests import Request
from starlette.responses import JSONResponse

from app import rt
from chat.components import left_pane, signin_overlay
from chat.layout import _versioned, common_scripts
from utils.session import get_currency, currency_symbol
from utils.i18n import t, get_lang
from chat.routes import _ensure_user, _list_sessions
from db import connect
from landing.components import TAILWIND_CONFIG, _favicon_links
from utils.llm import build_llm

log = logging.getLogger(__name__)


def _load_schema_snippet() -> str:
    """Build a schema snippet for the LLM from sql/schema.json."""
    import json as _json
    from pathlib import Path
    schema_path = Path(__file__).resolve().parent.parent / "sql" / "schema.json"
    if not schema_path.exists():
        return "-- schema.json not found; ask the user to run schema extraction"

    schema = _json.loads(schema_path.read_text())
    lines = [
        "-- PEHero read-only PostgreSQL schema. ONLY SELECT queries.",
        "-- Use schema-qualified names (pehero.*).\n",
    ]
    for table, info in schema.items():
        cols = info.get("columns", [])
        row_count = info.get("row_count", 0)
        enums = info.get("enums", {})

        col_parts = []
        for c in cols:
            part = c["name"]
            ctype = c.get("type", "")
            if "JSONB" in ctype:
                part += " JSONB"
            elif "DATE" in ctype or "TIMESTAMP" in ctype:
                part += " DATE"
            elif "NUMERIC" in ctype:
                part += f" {ctype}"
            if c["name"] in enums:
                vals = " | ".join(enums[c["name"]])
                part += f"  -- {vals}"
            col_parts.append(part)

        lines.append(f"{table} ({row_count} rows) (")
        lines.append("    " + ",\n    ".join(col_parts))
        lines.append(")\n")

    return "\n".join(lines)


SCHEMA_SNIPPET = _load_schema_snippet()


SAMPLE_QUERIES = [
    "Top 10 companies by LTM revenue, show sector",
    "Company count by deal stage",
    "Average EBITDA margin by sector",
    "Monthly revenue trend for DR VET",
    "Company count by city",
    "Revenue distribution by sub-sector",
    "Largest healthcare companies by employees",
    "Average revenue by sector, bar chart",
]


SYSTEM = f"""You translate plain-English questions into a single PostgreSQL SELECT
query against the PEHero schema below, and suggest a chart.

Rules:
- Return ONLY a JSON object with exactly these keys:
  {{ "sql": "...", "chart": "bar|line|scatter|pie|none", "x": "...", "y": "...", "color": "...", "title": "..." }}
- Never modify data. SELECT only.
- Use schema-qualified names (pehero.companies, pehero.financials, etc).
- Limit results sensibly (≤200 rows) unless a time-series needs more.
- For time series, order by the time column.
- For percentages like margins, already-percent values — leave them, don't multiply.

Schema:
{SCHEMA_SNIPPET}
"""


def _draft_sql(question: str) -> dict:
    llm = build_llm()
    resp = llm.invoke(f"{SYSTEM}\n\nQuestion: {question}\n\nJSON:").content
    # Find the JSON blob
    m = re.search(r"\{.*\}", resp, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON in model response: {resp[:400]}")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise ValueError(f"Bad JSON from model: {e} — {resp[:400]}")


def _guard_sql(sql: str) -> None:
    """Reject anything that isn't a single SELECT."""
    s = sql.strip().rstrip(";").strip()
    lowered = s.lower()
    if not lowered.startswith("select") and not lowered.startswith("with"):
        raise ValueError("Only SELECT / WITH queries are allowed.")
    banned = ["insert ", "update ", "delete ", "drop ", "truncate ",
              "alter ", "grant ", "revoke ", "create ", "copy ", ";"]
    for b in banned:
        if b in lowered:
            raise ValueError(f"Disallowed keyword in SQL: {b.strip()}")


def _run_sql(sql: str) -> pd.DataFrame:
    _guard_sql(sql)
    with connect() as conn:
        return pd.read_sql_query(sql, conn)


def _chart_for(df: pd.DataFrame, spec: dict) -> dict | None:
    if df.empty:
        return None
    kind = (spec.get("chart") or "").lower()
    x = spec.get("x")
    y = spec.get("y")
    color = spec.get("color") or None
    title = spec.get("title") or ""

    # Auto-fallback: if the model gave bad column names, try first two
    cols = list(df.columns)
    if x and x not in cols:
        x = cols[0]
    if y and y not in cols:
        y = next((c for c in cols[1:] if pd.api.types.is_numeric_dtype(df[c])), cols[-1])
    if color and color not in cols:
        color = None
    if not x:
        x = cols[0]
    if not y and len(cols) > 1:
        y = cols[1]

    try:
        if kind == "bar":
            fig = px.bar(df, x=x, y=y, color=color, title=title, barmode="group")
        elif kind == "line":
            fig = px.line(df, x=x, y=y, color=color, title=title, markers=True)
        elif kind == "scatter":
            fig = px.scatter(df, x=x, y=y, color=color, title=title)
        elif kind == "pie":
            fig = px.pie(df, names=x, values=y, title=title)
        else:
            return None
    except Exception as e:  # noqa: BLE001
        log.warning("plotly failed: %s", e)
        return None

    fig.update_layout(
        paper_bgcolor="#FFFFFF", plot_bgcolor="#F7F6F1",
        font=dict(family="Inter, system-ui", color="#14231B"),
        margin=dict(l=40, r=20, t=50, b=40),
        title=dict(font=dict(size=15)),
    )
    return json.loads(fig.to_json())


def _head(title: str) -> Head:
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
        Script(src="https://cdn.plot.ly/plotly-2.35.2.min.js"),
        Link(rel="stylesheet", href="/static/site.css"),
        Link(rel="stylesheet", href=_versioned("app.css")),
        Link(rel="stylesheet", href="/static/pipeline.css"),
    )


@rt("/app/analytics")
def analytics_home(sess):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)

    suggestions = Div(
        *[Button(q, cls="analytics-sugg", onclick=f"runAnalytics({q!r})")
          for q in SAMPLE_QUERIES],
        cls="analytics-suggestions",
    )

    body = Body(
        signin_overlay(),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="", current_currency=get_currency(sess), current_path="/app/analytics", lang=lang),
        Div(
            Div(
                Div(
                    Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    Span(t("analytics_title", lang), cls="chat-header-title"),
                    Span("·", cls="chat-header-dot"),
                    Span(t("analytics_sub", lang), cls="chat-header-agent"),
                    cls="chat-header-left",
                ),
                Div(A(t("chat_back", lang), href="/app", cls="back-to-chat-btn"),
                    cls="chat-header-actions"),
                cls="chat-header",
            ),
            Div(
                Div(
                    H2(t("analytics_h2", lang), cls="text-ink"),
                    P(t("analytics_body", lang), cls="text-ink-muted"),
                    cls="analytics-hero",
                ),
                Form(
                    Input(type="text", id="analytics-q", name="q",
                          placeholder="e.g. EV/EBITDA median by sector over the last 24 months",
                          onkeydown="if(event.key==='Enter'){event.preventDefault();runAnalytics()}"),
                    Button(t("analytics_run", lang), type="button", onclick="runAnalytics()"),
                    cls="analytics-form",
                ),
                suggestions,
                Div(id="analytics-result"),
                cls="analytics-wrap",
            ),
            cls="center-pane",
        ),
        Script(NotStr("""
            async function runAnalytics(q) {
                if (q) document.getElementById('analytics-q').value = q;
                const question = document.getElementById('analytics-q').value.trim();
                const out = document.getElementById('analytics-result');
                if (!question) return;
                out.innerHTML = '<div class="analytics-result"><div class="muted">Thinking…</div></div>';
                const r = await fetch('/app/analytics/run', {
                    method: 'POST',
                    body: new URLSearchParams({ q: question })
                });
                const data = await r.json();
                if (data.error) {
                    out.innerHTML = `<div class="analytics-error"><strong>Error:</strong> ${data.error}<br><pre style="margin-top:.5rem;font-size:.7rem;overflow-x:auto">${data.sql || ''}</pre></div>`;
                    return;
                }
                const chartId = 'chart-' + Math.random().toString(36).slice(2, 8);
                const tableHtml = data.table
                    ? `<div class="analytics-table-wrap">${data.table}</div>` : '';
                out.innerHTML = `
                    <div class="analytics-result">
                        <h3>${data.title || question}</h3>
                        <div class="sql">${data.sql}</div>
                        <div id="${chartId}" class="analytics-chart"></div>
                        ${tableHtml}
                    </div>`;
                if (data.figure) {
                    Plotly.newPlot(chartId, data.figure.data, data.figure.layout, {responsive: true});
                } else {
                    document.getElementById(chartId).innerHTML = '<p class="text-ink-muted text-sm">(No chart — showing table only.)</p>';
                }
            }
            window.runAnalytics = runAnalytics;
        """)),
        Script(src=_versioned("chat.js")),
        cls="bg-bg text-ink font-sans antialiased app pane-closed pipeline-app",
    )
    return Html(_head(t("analytics_title", lang)), body, lang=lang)


@rt("/app/analytics/run", methods=["POST"])
async def analytics_run(request: Request):
    form = await request.form()
    q = (form.get("q") or "").strip()
    if not q:
        return JSONResponse({"error": "Empty question."})

    try:
        spec = _draft_sql(q)
        sql = spec.get("sql", "").strip().rstrip(";")
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"LLM couldn't draft SQL: {e}"})

    try:
        df = _run_sql(sql)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"SQL failed: {e}", "sql": sql})

    fig = _chart_for(df, spec)
    table_html = df.head(50).to_html(index=False, classes="artifact-table",
                                     border=0, float_format=lambda x: f"{x:,.2f}" if isinstance(x, float) else str(x))

    return JSONResponse({
        "sql": sql,
        "title": spec.get("title") or q,
        "figure": fig,
        "rows": len(df),
        "table": table_html,
    })
