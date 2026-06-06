"""Daily Deals Digest — queries top 5 actionable deals, sends via Postmark.

Usage:
    python -m scripts.daily_deals                  # send to DAILY_DEALS_TO_EMAIL
    python -m scripts.daily_deals --to me@firm.com # override recipient
    python -m scripts.daily_deals --dry-run        # print HTML, don't send
"""

from __future__ import annotations

import argparse
import asyncio
import html as _html
from datetime import date

from db import fetch_all
from utils.config import settings
from utils.email import send_email


def _top_deals(n: int = 5) -> list[dict]:
    """Return the top N most actionable deals from the pipeline.

    Scoring: warm/hot seller intent first, then by EBITDA margin × growth,
    filtered to active stages (sourced → ic).
    """
    rows = fetch_all("""
        SELECT c.name, c.slug, c.sector, c.sub_sector, c.hq_city, c.country,
               c.revenue_ltm, c.ebitda_ltm, c.ebitda_margin, c.growth_rate,
               c.enterprise_value, c.ask_multiple, c.employees,
               c.ownership, c.deal_stage, c.seller_intent, c.description,
               ms.value AS sector_ev_ebitda
        FROM pehero.companies c
        LEFT JOIN LATERAL (
            SELECT value FROM pehero.market_signals
            WHERE sector = c.sector AND metric = 'ev_ebitda_median'
            ORDER BY as_of_date DESC LIMIT 1
        ) ms ON TRUE
        WHERE c.deal_stage IN ('sourced', 'screened', 'loi', 'diligence', 'ic')
          AND c.ebitda_margin > 0 AND c.ebitda_margin < 60
          AND (c.growth_rate IS NULL OR (c.growth_rate > -30 AND c.growth_rate < 100))
          AND c.revenue_ltm > 1000000
          AND c.ebitda_ltm > 0 AND c.ebitda_ltm <= c.revenue_ltm
        ORDER BY
            CASE c.seller_intent
                WHEN 'hot'  THEN 0
                WHEN 'warm' THEN 1
                ELSE 2
            END,
            COALESCE(c.ebitda_margin, 0) * GREATEST(COALESCE(c.growth_rate, 0), 0) DESC
        LIMIT %s
    """, (n,))
    return rows


def _fmt_eur(v) -> str:
    if v is None:
        return "n/a"
    if v >= 1_000_000:
        return f"€{v / 1_000_000:,.1f}M"
    return f"€{v:,.0f}"


def _pct(v) -> str:
    if v is None:
        return "n/a"
    return f"{v:.1f}%"


def _deal_rationale(d: dict) -> str:
    parts = []
    if d["seller_intent"] in ("hot", "warm"):
        parts.append(f"Seller intent is **{d['seller_intent']}**")
    if d["ebitda_margin"] and d["ebitda_margin"] > 20:
        parts.append(f"strong {_pct(d['ebitda_margin'])} EBITDA margin")
    if d["growth_rate"] and 0 < d["growth_rate"] < 500 and d["growth_rate"] > 10:
        parts.append(f"{_pct(d['growth_rate'])} revenue growth")
    if d["ask_multiple"] and d["sector_ev_ebitda"]:
        ask = float(d["ask_multiple"])
        median = float(d["sector_ev_ebitda"])
        if ask < median:
            parts.append(f"asking {ask:.1f}x vs {median:.1f}x sector median")
    if d["country"] not in ("LV", "LT", "EE") and d["ownership"] in ("founder", "family"):
        parts.append(f"{d['ownership']}-owned (succession opportunity)")
    if not parts:
        parts.append(f"{d['sector']} sector, {d['deal_stage']} stage")
    return "; ".join(parts)


def _fetch_news_sync(n: int = 5) -> list[dict]:
    from utils.news import fetch_news
    try:
        articles = asyncio.run(fetch_news())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        articles = loop.run_until_complete(fetch_news())
        loop.close()
    pe_icons = {"PEH", "BUY", "PEI", "FT", "BBG", "WSJ"}
    pe_articles = [a for a in articles if a.get("icon") in pe_icons]
    if len(pe_articles) < n:
        pe_articles = articles
    return pe_articles[:n]


def _render_news_html(articles: list[dict]) -> str:
    if not articles:
        return ""
    rows = ""
    for a in articles:
        esc = _html.escape
        title = esc(a["title"][:100])
        source = esc(a.get("source", ""))
        url = esc(a.get("url", "#"))
        summary = esc((a.get("summary") or "")[:120])
        if len(a.get("summary") or "") > 120:
            summary += "..."
        rows += f"""
        <tr>
            <td style="padding:10px 20px;border-bottom:1px solid #E5E7EB;">
                <a href="{url}" style="text-decoration:none;color:#14231B;font-size:13px;font-weight:600;line-height:1.3;">{title}</a>
                <div style="font-size:11px;color:#9CA3AF;margin-top:3px;">{source}</div>
            </td>
        </tr>"""

    return f"""
    <!-- News Section -->
    <tr>
        <td style="padding:20px 28px 8px;">
            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr><td style="border-top:2px solid #E5E7EB;padding-top:16px;">
                    <span style="font-size:14px;font-weight:700;color:#14231B;">Market News</span>
                    <span style="font-size:11px;color:#9CA3AF;margin-left:8px;">PE &amp; Financial</span>
                </td></tr>
            </table>
        </td>
    </tr>
    <tr><td style="padding:0 8px;">
        <table cellpadding="0" cellspacing="0" border="0" width="100%">
        {rows}
        </table>
    </td></tr>"""


def _render_html(deals: list[dict], news: list[dict] | None = None) -> str:
    today = date.today().strftime("%B %d, %Y")
    rows_html = ""
    for i, d in enumerate(deals, 1):
        esc = _html.escape
        name = esc(d["name"])
        sector = esc(f"{d['sector']} · {d['sub_sector']}" if d.get("sub_sector") else d["sector"])
        location = esc(f"{d['hq_city']}, {d['country']}" if d.get("hq_city") else d.get("country", ""))
        rationale = _deal_rationale(d).replace("**", "<strong>", 1).replace("**", "</strong>", 1)
        desc = esc((d.get("description") or "")[:120])
        if len(d.get("description") or "") > 120:
            desc += "..."

        stage_colors = {
            "sourced": "#6B7280", "screened": "#2563EB",
            "loi": "#D97706", "diligence": "#7C3AED", "ic": "#059669",
        }
        stage_color = stage_colors.get(d["deal_stage"], "#6B7280")
        intent_colors = {"hot": "#DC2626", "warm": "#F59E0B", "cold": "#9CA3AF"}
        intent_color = intent_colors.get(d["seller_intent"], "#9CA3AF")

        rows_html += f"""
        <tr>
            <td style="padding:16px 20px;border-bottom:1px solid #E5E7EB;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                    <tr>
                        <td>
                            <span style="font-size:11px;font-weight:700;color:#1F5D43;font-family:'JetBrains Mono',monospace;">#{i}</span>
                            <span style="font-size:16px;font-weight:700;color:#14231B;margin-left:8px;">{name}</span>
                            <span style="display:inline-block;background:{stage_color};color:#fff;font-size:10px;font-weight:600;padding:2px 8px;border-radius:10px;margin-left:8px;text-transform:uppercase;letter-spacing:0.05em;">{esc(d["deal_stage"])}</span>
                            <span style="display:inline-block;background:{intent_color};color:#fff;font-size:10px;font-weight:600;padding:2px 8px;border-radius:10px;margin-left:4px;text-transform:uppercase;letter-spacing:0.05em;">{esc(d["seller_intent"] or "cold")}</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding-top:6px;font-size:13px;color:#6B7280;">{sector} · {location}</td>
                    </tr>
                    <tr>
                        <td style="padding-top:8px;">
                            <table cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td style="padding-right:20px;">
                                        <div style="font-size:10px;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.1em;">Revenue LTM</div>
                                        <div style="font-size:15px;font-weight:600;color:#14231B;">{_fmt_eur(d["revenue_ltm"])}</div>
                                    </td>
                                    <td style="padding-right:20px;">
                                        <div style="font-size:10px;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.1em;">EBITDA LTM</div>
                                        <div style="font-size:15px;font-weight:600;color:#14231B;">{_fmt_eur(d["ebitda_ltm"])}</div>
                                    </td>
                                    <td style="padding-right:20px;">
                                        <div style="font-size:10px;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.1em;">EV</div>
                                        <div style="font-size:15px;font-weight:600;color:#14231B;">{_fmt_eur(d["enterprise_value"])}</div>
                                    </td>
                                    <td style="padding-right:20px;">
                                        <div style="font-size:10px;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.1em;">Growth</div>
                                        <div style="font-size:15px;font-weight:600;color:#14231B;">{_pct(d["growth_rate"])}</div>
                                    </td>
                                    <td>
                                        <div style="font-size:10px;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.1em;">Ask</div>
                                        <div style="font-size:15px;font-weight:600;color:#14231B;">{f'{float(d["ask_multiple"]):.1f}x' if d["ask_multiple"] else "n/a"}</div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding-top:8px;font-size:13px;color:#374151;line-height:1.4;">
                            <strong style="color:#1F5D43;">Why now:</strong> {rationale}
                        </td>
                    </tr>
                    {"<tr><td style='padding-top:4px;font-size:12px;color:#6B7280;font-style:italic;'>" + desc + "</td></tr>" if desc else ""}
                </table>
            </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#F3F4F6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#F3F4F6;">
<tr><td align="center" style="padding:24px 16px;">
<table cellpadding="0" cellspacing="0" border="0" width="640" style="max-width:640px;background:#FFFFFF;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
    <!-- Header -->
    <tr>
        <td style="background:#14231B;padding:24px 28px;">
            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr>
                    <td>
                        <span style="color:#1F5D43;font-size:22px;font-weight:700;">◆</span>
                        <span style="color:#FFFFFF;font-size:20px;font-weight:700;margin-left:6px;">PEHero</span>
                        <span style="color:#CFE5DA;font-size:11px;font-weight:600;background:rgba(31,93,67,0.4);padding:2px 8px;border-radius:4px;margin-left:8px;text-transform:uppercase;letter-spacing:0.08em;">Daily Deals</span>
                    </td>
                    <td align="right" style="color:#9CA3AF;font-size:12px;font-family:'JetBrains Mono',monospace;">{today}</td>
                </tr>
            </table>
        </td>
    </tr>
    <!-- Intro -->
    <tr>
        <td style="padding:20px 28px 12px;font-size:14px;color:#374151;line-height:1.5;">
            Good morning — here are today's <strong>top {len(deals)} actionable deals</strong> from your pipeline, ranked by seller intent and financial attractiveness.
        </td>
    </tr>
    <!-- Deals -->
    {rows_html}
    <!-- CTA -->
    <tr>
        <td align="center" style="padding:24px 28px;">
            <a href="https://pehero.fyi/app/pipeline" style="display:inline-block;background:#1F5D43;color:#FFFFFF;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">Open Pipeline →</a>
        </td>
    </tr>
    {_render_news_html(news) if news else ""}
    <!-- Footer -->
    <tr>
        <td style="background:#F9FAFB;padding:16px 28px;border-top:1px solid #E5E7EB;">
            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr>
                    <td style="font-size:11px;color:#9CA3AF;">PEHero · Your Private Equity AI Agent Squad</td>
                    <td align="right" style="font-size:11px;color:#9CA3AF;font-family:'JetBrains Mono',monospace;">pehero.fyi</td>
                </tr>
            </table>
        </td>
    </tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def _render_text(deals: list[dict], news: list[dict] | None = None) -> str:
    today = date.today().strftime("%B %d, %Y")
    lines = [f"PEHero Daily Deals — {today}", "=" * 40, ""]
    for i, d in enumerate(deals, 1):
        lines.append(f"#{i}  {d['name']}  [{d['deal_stage']}]  [{d['seller_intent']}]")
        lines.append(f"    {d['sector']} · {d.get('hq_city', '')}, {d.get('country', '')}")
        lines.append(f"    Rev: {_fmt_eur(d['revenue_ltm'])}  EBITDA: {_fmt_eur(d['ebitda_ltm'])}  EV: {_fmt_eur(d['enterprise_value'])}  Growth: {_pct(d['growth_rate'])}")
        lines.append(f"    Why: {_deal_rationale(d)}")
        lines.append("")
    lines.append("Open pipeline: https://pehero.fyi/app/pipeline")
    if news:
        lines.append("")
        lines.append("Market News")
        lines.append("-" * 40)
        for a in news:
            lines.append(f"  {a['source']}: {a['title']}")
            lines.append(f"  {a['url']}")
            lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Send daily deals digest email")
    parser.add_argument("--to", default=None, help="Override recipient email")
    parser.add_argument("--dry-run", action="store_true", help="Print HTML, don't send")
    parser.add_argument("--count", type=int, default=5, help="Number of deals")
    args = parser.parse_args()

    deals = _top_deals(args.count)
    if not deals:
        print("No active deals in pipeline — skipping email.")
        return

    news = _fetch_news_sync(5)
    html_body = _render_html(deals, news)
    text_body = _render_text(deals, news)
    today = date.today().strftime("%b %d")
    subject = f"PEHero Daily Deals — {today} — {len(deals)} actionable opportunities"

    if args.dry_run:
        print(html_body)
        print("\n--- TEXT ---\n")
        print(text_body)
        return

    to = args.to or settings().daily_deals_to_email
    if not to:
        print("No recipient — set DAILY_DEALS_TO_EMAIL or use --to")
        return

    result = send_email(to=to, subject=subject, html_body=html_body, text_body=text_body)
    print(f"Sent to {to} — MessageID: {result.get('MessageID', 'n/a')}")


if __name__ == "__main__":
    main()
