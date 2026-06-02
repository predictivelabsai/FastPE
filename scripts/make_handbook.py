"""
Generate PE Handbook as PDF and EPUB.

Produces Plotly charts as PNGs, injects them into the markdown,
then converts to PDF (via pandoc + wkhtmltopdf) and EPUB.

Usage:
    python -m scripts.make_handbook           # both PDF and EPUB
    python -m scripts.make_handbook --pdf     # PDF only
    python -m scripts.make_handbook --epub    # EPUB only
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

ROOT = Path(__file__).resolve().parent.parent
HANDBOOK_MD = ROOT / "docs" / "pe-handbook.md"
OUT_DIR = ROOT / "docs"
CHART_DIR = ROOT / "docs" / "charts"


# ── Chart definitions ──────────────────────────────────────────────


def chart_j_curve(out: Path):
    years = list(range(0, 11))
    irr = [0, -8, -15, -18, -12, -5, 0, 8, 13, 17, 18]
    tvpi = [1.0, 0.0, 0.0, 0.3, 0.4, 0.7, 1.0, 1.5, 1.7, 2.1, 2.3]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years, y=irr, mode="lines+markers", name="Net IRR (%)",
        line=dict(color="#1a3c6e", width=3),
        marker=dict(size=8),
    ))
    fig.add_trace(go.Scatter(
        x=years, y=tvpi, mode="lines+markers", name="TVPI (×)",
        yaxis="y2",
        line=dict(color="#2ecc71", width=3, dash="dot"),
        marker=dict(size=8, symbol="diamond"),
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_layout(
        title="The J-Curve: PE Fund Returns Over Time",
        xaxis_title="Fund Year",
        yaxis=dict(title="Net IRR (%)", range=[-25, 25]),
        yaxis2=dict(title="TVPI (×)", overlaying="y", side="right", range=[-0.5, 3.0]),
        template="plotly_white",
        width=900, height=500,
        legend=dict(x=0.02, y=0.98),
        font=dict(size=14),
    )
    fig.write_image(str(out), scale=2)


def chart_value_creation_bridge(out: Path):
    categories = [
        "Entry equity", "EBITDA growth", "Multiple expansion",
        "Debt paydown", "Txn costs", "Exit equity",
    ]
    values = [6.5, 9.0, 3.9, 7.9, -0.4, None]
    measures = ["absolute", "relative", "relative", "relative", "relative", "total"]

    fig = go.Figure(go.Waterfall(
        x=categories, y=values, measure=measures,
        connector=dict(line=dict(color="rgba(0,0,0,0.3)", width=1)),
        increasing=dict(marker=dict(color="#2ecc71")),
        decreasing=dict(marker=dict(color="#e74c3c")),
        totals=dict(marker=dict(color="#1a3c6e")),
        text=[f"€{v:.1f}M" if v else "" for v in [6.5, 9.0, 3.9, 7.9, -0.4, 26.8]],
        textposition="outside",
    ))
    fig.update_layout(
        title="LBO Value Creation Bridge — NordFreight (€M)",
        yaxis_title="Equity Value (€M)",
        template="plotly_white",
        width=900, height=500,
        font=dict(size=14),
        showlegend=False,
    )
    fig.write_image(str(out), scale=2)


def chart_sensitivity_heatmap(out: Path):
    exit_multiples = ["5.5×", "6.0×", "6.5×", "7.0×", "7.5×"]
    ebitda_cagr = ["5%", "8%", "10%", "12%", "15%"]
    irr_matrix = [
        [13, 16, 19, 22, 24],
        [18, 21, 24, 27, 29],
        [22, 25, 28, 33, 34],
        [25, 28, 31, 34, 37],
        [30, 33, 36, 38, 41],
    ]

    fig = go.Figure(go.Heatmap(
        z=irr_matrix,
        x=exit_multiples,
        y=ebitda_cagr,
        text=[[f"{v}%" for v in row] for row in irr_matrix],
        texttemplate="%{text}",
        textfont=dict(size=14),
        colorscale=[
            [0.0, "#e74c3c"],
            [0.3, "#f39c12"],
            [0.5, "#f1c40f"],
            [0.7, "#2ecc71"],
            [1.0, "#1a3c6e"],
        ],
        colorbar=dict(title="IRR (%)"),
    ))
    fig.update_layout(
        title="IRR Sensitivity: Exit Multiple vs. EBITDA Growth",
        xaxis_title="Exit EV/EBITDA Multiple",
        yaxis_title="EBITDA CAGR",
        template="plotly_white",
        width=800, height=500,
        font=dict(size=14),
    )
    fig.write_image(str(out), scale=2)


def chart_fund_portfolio_returns(out: Path):
    deals = [f"Deal {i}" for i in range(1, 11)]
    moics = [3.0, 2.5, 3.0, 0.0, 2.0, 3.0, 2.5, 3.5, 3.0, 2.5]
    colors = ["#2ecc71" if m > 0 else "#e74c3c" for m in moics]

    fig = go.Figure(go.Bar(
        x=deals, y=moics, marker_color=colors,
        text=[f"{m:.1f}×" for m in moics],
        textposition="outside",
    ))
    fig.add_hline(y=2.6, line_dash="dash", line_color="#1a3c6e",
                  annotation_text="Fund average: 2.6×", annotation_position="top right")
    fig.add_hline(y=1.0, line_dash="dot", line_color="gray",
                  annotation_text="Breakeven", annotation_position="bottom right")
    fig.update_layout(
        title="Baltic Growth Fund II — Deal-Level Returns (MOIC)",
        yaxis_title="MOIC (×)",
        template="plotly_white",
        width=900, height=500,
        font=dict(size=14),
    )
    fig.write_image(str(out), scale=2)


def chart_deal_funnel(out: Path):
    stages = [
        "Reviewed", "Screens passed", "Mgmt meetings",
        "LOIs", "DD completed", "Closed",
    ]
    values = [800, 200, 60, 15, 6, 3]

    fig = go.Figure(go.Funnel(
        y=stages, x=values,
        textinfo="value+percent initial",
        marker=dict(color=[
            "#1a3c6e", "#2471a3", "#2e86c1",
            "#2ecc71", "#27ae60", "#1e8449",
        ]),
    ))
    fig.update_layout(
        title="PE Deal Funnel — Annual Pipeline",
        template="plotly_white",
        width=800, height=500,
        font=dict(size=14),
    )
    fig.write_image(str(out), scale=2)


def chart_baltic_pe_growth(out: Path):
    years = [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
    deal_count = [18, 22, 28, 35, 42, 38, 52, 61, 68, 75, 82]
    deal_value = [120, 180, 250, 380, 520, 410, 680, 850, 920, 1050, 1200]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years, y=deal_value, name="Deal value (€M)",
        marker_color="#1a3c6e", opacity=0.7,
    ))
    fig.add_trace(go.Scatter(
        x=years, y=deal_count, name="Deal count",
        yaxis="y2", mode="lines+markers",
        line=dict(color="#2ecc71", width=3),
        marker=dict(size=8),
    ))
    fig.update_layout(
        title="Baltic PE Market Growth (Illustrative)",
        xaxis_title="Year",
        yaxis=dict(title="Deal Value (€M)"),
        yaxis2=dict(title="Number of Deals", overlaying="y", side="right"),
        template="plotly_white",
        width=900, height=500,
        legend=dict(x=0.02, y=0.98),
        font=dict(size=14),
    )
    fig.write_image(str(out), scale=2)


def chart_ai_roi(out: Path):
    initiatives = [
        "Demand\nforecasting", "Invoice\nprocessing", "Order status\nchatbot",
        "Dynamic\npricing", "Predictive\nmaintenance", "Churn\nprediction",
    ]
    investment = [60, 40, 25, 80, 35, 30]
    annual_return = [180, 120, 80, 250, 60, 150]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=initiatives, y=investment, name="Investment (€K)",
        marker_color="#e74c3c", opacity=0.8,
    ))
    fig.add_trace(go.Bar(
        x=initiatives, y=annual_return, name="Annual EBITDA Impact (€K)",
        marker_color="#2ecc71", opacity=0.8,
    ))
    fig.update_layout(
        title="AI Investment vs. Annual Return — Portfolio Company Example",
        yaxis_title="€ Thousands",
        barmode="group",
        template="plotly_white",
        width=900, height=500,
        legend=dict(x=0.02, y=0.98),
        font=dict(size=14),
    )
    fig.write_image(str(out), scale=2)


def chart_balticmed_trajectory(out: Path):
    years = ["Year 0", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5"]
    revenue = [6.5, 7.2, 10.5, 13.8, 16.5, 18.0]
    ebitda = [1.48, 1.73, 2.6, 3.7, 4.6, 5.2]
    debt = [5.2, 4.3, 3.8, 2.9, 1.8, 0.8]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years, y=revenue, name="Revenue (€M)",
        marker_color="#2e86c1", opacity=0.7,
    ))
    fig.add_trace(go.Scatter(
        x=years, y=ebitda, name="EBITDA (€M)",
        mode="lines+markers",
        line=dict(color="#2ecc71", width=3),
        marker=dict(size=10),
    ))
    fig.add_trace(go.Scatter(
        x=years, y=debt, name="Debt (€M)",
        mode="lines+markers",
        line=dict(color="#e74c3c", width=3, dash="dash"),
        marker=dict(size=10, symbol="triangle-down"),
    ))
    fig.update_layout(
        title="BalticMed — 5-Year Financial Trajectory",
        yaxis_title="€ Millions",
        template="plotly_white",
        width=900, height=500,
        legend=dict(x=0.02, y=0.98),
        font=dict(size=14),
    )
    fig.write_image(str(out), scale=2)


def chart_exit_bridge(out: Path):
    categories = [
        "Entry equity", "Organic EBITDA", "Add-on EBITDA",
        "Multiple expansion", "Debt paydown",
        "Synergies & margin", "Exit equity",
    ]
    values = [6.0, 11.2, 8.8, 14.6, 4.4, 4.7, None]
    measures = [
        "absolute", "relative", "relative",
        "relative", "relative", "relative", "total",
    ]

    fig = go.Figure(go.Waterfall(
        x=categories, y=values, measure=measures,
        connector=dict(line=dict(color="rgba(0,0,0,0.3)", width=1)),
        increasing=dict(marker=dict(color="#2ecc71")),
        totals=dict(marker=dict(color="#1a3c6e")),
        text=[
            "€6.0M", "€11.2M", "€8.8M", "€14.6M",
            "€4.4M", "€4.7M", "€49.7M",
        ],
        textposition="outside",
    ))
    fig.update_layout(
        title="BalticMed — Exit Value Creation Bridge (€M)",
        yaxis_title="Equity Value (€M)",
        template="plotly_white",
        width=1000, height=500,
        font=dict(size=13),
        showlegend=False,
    )
    fig.write_image(str(out), scale=2)


CHARTS = {
    "j_curve": chart_j_curve,
    "value_creation_bridge": chart_value_creation_bridge,
    "sensitivity_heatmap": chart_sensitivity_heatmap,
    "fund_portfolio_returns": chart_fund_portfolio_returns,
    "deal_funnel": chart_deal_funnel,
    "baltic_pe_growth": chart_baltic_pe_growth,
    "ai_roi": chart_ai_roi,
    "balticmed_trajectory": chart_balticmed_trajectory,
    "exit_bridge": chart_exit_bridge,
}


# ── Markdown injection ─────────────────────────────────────────────

CHART_PLACEMENTS = {
    "j_curve": "PE fund returns follow a characteristic",
    "value_creation_bridge": "**Value creation bridge:**",
    "sensitivity_heatmap": "**IRR Sensitivity: Exit Multiple vs. EBITDA Growth**",
    "fund_portfolio_returns": "Note: Deal 4 was a total loss",
    "deal_funnel": "A typical mid-market PE fund reviews",
    "baltic_pe_growth": "### Market Dynamics",
    "ai_roi": "**Impact on valuation:**",
    "balticmed_trajectory": "**Year-by-year financial trajectory:**",
    "exit_bridge": "**Value creation bridge (€M):**",
}


def inject_charts(md_text: str, chart_dir: Path) -> str:
    for chart_name, anchor_text in CHART_PLACEMENTS.items():
        chart_path = chart_dir / f"{chart_name}.png"
        if not chart_path.exists():
            continue
        img_tag = f"\n\n![{chart_name.replace('_', ' ').title()}]({chart_path})\n\n"
        idx = md_text.find(anchor_text)
        if idx != -1:
            md_text = md_text[:idx] + img_tag + md_text[idx:]
    return md_text


# ── Build pipeline ─────────────────────────────────────────────────


def generate_charts():
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    for name, fn in CHARTS.items():
        out = CHART_DIR / f"{name}.png"
        print(f"  Generating {name}.png ...")
        fn(out)
    print(f"  {len(CHARTS)} charts saved to {CHART_DIR}/")


def build_pdf():
    print("\nBuilding PDF ...")
    md_text = HANDBOOK_MD.read_text()
    enriched = inject_charts(md_text, CHART_DIR)

    with tempfile.NamedTemporaryFile(
        suffix=".md", mode="w", delete=False, dir=str(OUT_DIR)
    ) as tmp:
        tmp.write(enriched)
        tmp_path = Path(tmp.name)

    css_path = OUT_DIR / "_handbook.css"
    css_path.write_text(
        "body { font-size: 11pt; line-height: 1.6; font-family: Georgia, serif; }\n"
        "h1 { font-size: 22pt; margin-top: 40pt; page-break-before: always; }\n"
        "h2 { font-size: 18pt; margin-top: 30pt; page-break-before: always; }\n"
        "h3 { font-size: 14pt; margin-top: 20pt; }\n"
        "h4 { font-size: 12pt; margin-top: 15pt; }\n"
        "table { font-size: 9.5pt; border-collapse: collapse; width: 100%; margin: 12pt 0; }\n"
        "th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; }\n"
        "th { background-color: #1a3c6e; color: white; }\n"
        "img { max-width: 100%; height: auto; margin: 16pt 0; }\n"
        "code { font-size: 9pt; }\n"
        "pre { font-size: 9pt; background: #f5f5f5; padding: 12px; }\n"
        "blockquote { border-left: 3px solid #1a3c6e; padding-left: 12px; color: #444; }\n"
    )

    out_pdf = OUT_DIR / "pe-handbook.pdf"
    cmd = [
        "pandoc", str(tmp_path),
        "-o", str(out_pdf),
        "--pdf-engine=wkhtmltopdf",
        "--pdf-engine-opt=--enable-local-file-access",
        "--css", str(css_path),
        "-V", "margin-top=25mm",
        "-V", "margin-bottom=25mm",
        "-V", "margin-left=30mm",
        "-V", "margin-right=25mm",
        "--metadata", "title=The Private Equity Handbook",
        "--metadata", "author=PE Hero (pehero.fyi)",
        "--toc",
        "--toc-depth=2",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    tmp_path.unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"  PDF error: {result.stderr[:500]}")
        return False
    print(f"  PDF saved: {out_pdf} ({out_pdf.stat().st_size // 1024} KB)")
    return True


def build_epub():
    print("\nBuilding EPUB ...")
    md_text = HANDBOOK_MD.read_text()
    enriched = inject_charts(md_text, CHART_DIR)

    with tempfile.NamedTemporaryFile(
        suffix=".md", mode="w", delete=False, dir=str(OUT_DIR)
    ) as tmp:
        tmp.write(enriched)
        tmp_path = Path(tmp.name)

    out_epub = OUT_DIR / "pe-handbook.epub"
    cmd = [
        "pandoc", str(tmp_path),
        "-o", str(out_epub),
        "--metadata", "title=The Private Equity Handbook",
        "--metadata", "author=PE Hero (pehero.fyi)",
        "--toc",
        "--toc-depth=2",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    tmp_path.unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"  EPUB error: {result.stderr[:500]}")
        return False
    print(f"  EPUB saved: {out_epub} ({out_epub.stat().st_size // 1024} KB)")
    return True


def main():
    parser = argparse.ArgumentParser(description="Build PE Handbook PDF/EPUB")
    parser.add_argument("--pdf", action="store_true", help="PDF only")
    parser.add_argument("--epub", action="store_true", help="EPUB only")
    args = parser.parse_args()

    both = not args.pdf and not args.epub

    print("Generating charts ...")
    generate_charts()

    ok = True
    if both or args.pdf:
        ok = build_pdf() and ok
    if both or args.epub:
        ok = build_epub() and ok

    if ok:
        print("\nDone.")
    else:
        print("\nCompleted with errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
