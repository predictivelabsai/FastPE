"""Daily Deals Digest — top actionable deals + a Featured Sector screen,
sent via Postmark.

The Featured Sector block runs the taxonomy-driven Baltic health / dental /
dermatology screen (evals.run_screen_eval.screen_db) — founder/family-owned
clinics, €3-10M revenue — and backlinks into the PEHero app. It is included in
both the scheduled daemon send and manual sends.

Usage:
    python -m scripts.daily_deals                  # send to all opted-in users
    python -m scripts.daily_deals --to me@firm.com # override: single recipient
    python -m scripts.daily_deals --dry-run        # print HTML, don't send
"""

from __future__ import annotations

import argparse
import asyncio
import html as _html
import logging
import secrets
from datetime import date

from db import connect, fetch_all
from utils.config import settings
from utils.email import send_email

log = logging.getLogger(__name__)

SERVICE_URL = settings().service_url.rstrip("/")


def _top_deals(n: int = 5) -> list[dict]:
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


# ── Featured Sector (Baltic health/dental/dermatology screen) ──────────

FEATURED_SUBTITLE = ("Baltic health, dental &amp; dermatology clinics · "
                     "founder / family-owned · €3&ndash;10M revenue")


def _featured_sector(limit: int = 6, scan_cap: int = 200) -> dict:
    """Run the Baltic health/dental/dermatology screen for the email's Featured
    Sector block. Reuses the taxonomy-driven screen in evals.run_screen_eval so
    the email and the eval stay in lockstep. Degrades to an empty block."""
    try:
        from evals.run_screen_eval import screen_db
        res = screen_db(limit=scan_cap)
        companies = res.get("companies", []) or []
        return {"companies": companies[:limit],
                "total": res.get("count", len(companies)),
                "note": res.get("note", "")}
    except Exception as e:  # noqa: BLE001 — Featured Sector is optional in the email
        log.warning("featured sector screen failed: %s", e)
        return {"companies": [], "total": 0, "note": str(e)[:160]}


def _render_featured_sector_html(featured: dict | None) -> str:
    companies = (featured or {}).get("companies") or []
    if not companies:
        return ""
    esc = _html.escape
    total = (featured or {}).get("total", len(companies))
    rows = ""
    for c in companies:
        name = esc(c.get("name", ""))
        country = esc((c.get("country") or "").upper())
        sub = esc(c.get("sub_sector") or c.get("sector") or "")
        ownership = esc((c.get("ownership") or "").replace("_", " "))
        rev = _fmt_eur(c.get("revenue_ltm"))
        rows += f"""
        <tr>
            <td style="padding:10px 20px;border-bottom:1px solid #E5E7EB;">
                <span style="font-size:14px;font-weight:700;color:#14231B;">{name}</span>
                <span style="display:inline-block;background:#1F5D43;color:#fff;font-size:10px;font-weight:600;padding:1px 7px;border-radius:10px;margin-left:6px;">{country}</span>
                <span style="display:inline-block;background:#E5EFE9;color:#1F5D43;font-size:10px;font-weight:600;padding:1px 7px;border-radius:10px;margin-left:4px;text-transform:capitalize;">{ownership}</span>
                <div style="font-size:12px;color:#6B7280;margin-top:3px;">{sub} · <strong style="color:#14231B;">{rev}</strong> revenue</div>
            </td>
        </tr>"""

    backlink = f"{SERVICE_URL}/app/companies?sector=healthcare"
    return f"""
    <!-- Featured Sector -->
    <tr>
        <td style="padding:20px 28px 8px;">
            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr><td style="border-top:2px solid #E5E7EB;padding-top:16px;">
                    <span style="font-size:14px;font-weight:700;color:#14231B;">Featured Sector</span>
                    <span style="font-size:11px;color:#9CA3AF;margin-left:8px;">{FEATURED_SUBTITLE}</span>
                </td></tr>
                <tr><td style="font-size:12px;color:#6B7280;padding-top:4px;">{total} matching targets — top {len(companies)} by revenue:</td></tr>
            </table>
        </td>
    </tr>
    <tr><td style="padding:0 8px;">
        <table cellpadding="0" cellspacing="0" border="0" width="100%">
        {rows}
        </table>
    </td></tr>
    <tr>
        <td align="center" style="padding:14px 28px 4px;">
            <a href="{backlink}" style="display:inline-block;background:#14231B;color:#FFFFFF;padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:600;font-size:13px;">Explore this sector in PEHero →</a>
        </td>
    </tr>"""


def _render_html(deals: list[dict], news: list[dict] | None = None,
                 unsubscribe_url: str = "", featured: dict | None = None) -> str:
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

    unsub_html = ""
    if unsubscribe_url:
        unsub_html = f' · <a href="{_html.escape(unsubscribe_url)}" style="color:#9CA3AF;text-decoration:underline;">Unsubscribe</a>'

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
            {("Good morning — here are today's <strong>top " + str(len(deals)) + " actionable deals</strong> from your pipeline, ranked by seller intent and financial attractiveness." if deals else "Good morning — no new pipeline deals today. Here's the <strong>Featured Sector</strong> screen we're tracking for you.")}
        </td>
    </tr>
    <!-- Deals -->
    {rows_html}
    <!-- CTA -->
    <tr>
        <td align="center" style="padding:24px 28px;">
            <a href="{SERVICE_URL}/app/pipeline" style="display:inline-block;background:#1F5D43;color:#FFFFFF;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">Open Pipeline →</a>
        </td>
    </tr>
    {_render_featured_sector_html(featured) if featured else ""}
    {_render_news_html(news) if news else ""}
    <!-- Footer -->
    <tr>
        <td style="background:#F9FAFB;padding:16px 28px;border-top:1px solid #E5E7EB;">
            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr>
                    <td style="font-size:11px;color:#9CA3AF;">PEHero · Your Private Equity AI Agent Squad{unsub_html}</td>
                    <td align="right" style="font-size:11px;color:#9CA3AF;font-family:'JetBrains Mono',monospace;">pehero.chat</td>
                </tr>
            </table>
        </td>
    </tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def _render_text(deals: list[dict], news: list[dict] | None = None,
                 unsubscribe_url: str = "", featured: dict | None = None) -> str:
    today = date.today().strftime("%B %d, %Y")
    lines = [f"PEHero Daily Deals — {today}", "=" * 40, ""]
    for i, d in enumerate(deals, 1):
        lines.append(f"#{i}  {d['name']}  [{d['deal_stage']}]  [{d['seller_intent']}]")
        lines.append(f"    {d['sector']} · {d.get('hq_city', '')}, {d.get('country', '')}")
        lines.append(f"    Rev: {_fmt_eur(d['revenue_ltm'])}  EBITDA: {_fmt_eur(d['ebitda_ltm'])}  EV: {_fmt_eur(d['enterprise_value'])}  Growth: {_pct(d['growth_rate'])}")
        lines.append(f"    Why: {_deal_rationale(d)}")
        lines.append("")
    lines.append(f"Open pipeline: {SERVICE_URL}/app/pipeline")
    if featured and featured.get("companies"):
        lines.append("")
        lines.append("Featured Sector — Baltic health, dental & dermatology clinics, "
                     "founder/family-owned, €3-10M revenue")
        lines.append("-" * 40)
        for c in featured["companies"]:
            rev = _fmt_eur(c.get("revenue_ltm"))
            lines.append(f"  {c.get('name','')} [{(c.get('country') or '').upper()}] "
                         f"{c.get('sub_sector') or c.get('sector') or ''} · "
                         f"{(c.get('ownership') or '')} · {rev}")
        lines.append(f"  Explore: {SERVICE_URL}/app/companies?sector=healthcare")
    if news:
        lines.append("")
        lines.append("Market News")
        lines.append("-" * 40)
        for a in news:
            lines.append(f"  {a['source']}: {a['title']}")
            lines.append(f"  {a['url']}")
            lines.append("")
    if unsubscribe_url:
        lines.append(f"\nUnsubscribe: {unsubscribe_url}")
    return "\n".join(lines)


# ── Multi-recipient logic ──────────────────────────────────────────

def _get_recipients() -> list[dict]:
    """Return all verified users with notify_new_deals enabled."""
    rows = fetch_all("""
        SELECT u.id, u.email, p.unsubscribe_token
        FROM pehero.users u
        JOIN pehero.user_preferences p ON u.id = p.user_id
        WHERE p.notify_new_deals = TRUE
          AND u.is_verified = TRUE
    """)
    # Backfill missing unsubscribe tokens
    need_token = [r for r in rows if not r["unsubscribe_token"]]
    if need_token:
        with connect() as conn, conn.cursor() as cur:
            for r in need_token:
                token = secrets.token_urlsafe(32)
                cur.execute(
                    "UPDATE pehero.user_preferences SET unsubscribe_token = %s WHERE user_id = %s",
                    (token, r["id"]),
                )
                r["unsubscribe_token"] = token
            conn.commit()
    return rows


def _record_send(user_id: int, subject: str, message_id: str) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO pehero.digest_sends (user_id, subject, message_id) VALUES (%s, %s, %s)",
            (user_id, subject, message_id),
        )
        conn.commit()


def send_to_all_users(deals: list[dict], news: list[dict] | None = None,
                      featured: dict | None = None) -> int:
    """Send daily deals digest to all opted-in users. Returns send count.

    When `featured` is None it is computed once here, so the scheduled daemon
    send (main.py) includes the Featured Sector block without extra wiring.
    """
    recipients = _get_recipients()
    if not recipients:
        log.info("No opted-in users — skipping daily deals")
        return 0

    if featured is None:
        featured = _featured_sector()
        log.info("Featured Sector: %d targets in universe", featured.get("total", 0))

    today = date.today().strftime("%b %d")
    subject = f"PEHero Daily Deals — {today} — {len(deals)} actionable opportunities"
    sent = 0

    for r in recipients:
        unsub_url = f"{SERVICE_URL}/auth/unsubscribe/{r['unsubscribe_token']}"
        html_body = _render_html(deals, news, unsubscribe_url=unsub_url, featured=featured)
        text_body = _render_text(deals, news, unsubscribe_url=unsub_url, featured=featured)
        try:
            result = send_email(
                to=r["email"], subject=subject,
                html_body=html_body, text_body=text_body, tag="daily_deals",
            )
            msg_id = result.get("MessageID", "")
            if msg_id:
                _record_send(r["id"], subject, msg_id)
                sent += 1
                log.info("Daily deals sent to %s — %s", r["email"], msg_id)
            else:
                log.warning("Daily deals to %s — no MessageID: %s", r["email"], result)
        except Exception:
            log.exception("Daily deals failed for %s", r["email"])

    log.info("Daily deals digest sent to %d/%d users", sent, len(recipients))
    return sent


def main():
    parser = argparse.ArgumentParser(description="Send daily deals digest email")
    parser.add_argument("--to", default=None, help="Single recipient (overrides DB query)")
    parser.add_argument("--dry-run", action="store_true", help="Print HTML, don't send")
    parser.add_argument("--count", type=int, default=5, help="Number of deals")
    args = parser.parse_args()

    deals = _top_deals(args.count)
    news = _fetch_news_sync(5)
    featured = _featured_sector()
    if featured.get("companies"):
        print(f"Featured Sector: {featured['total']} targets — showing top {len(featured['companies'])}")
    elif featured.get("note"):
        print(f"Featured Sector unavailable: {featured['note']}")

    # Send if there's anything to show — deals OR the Featured Sector screen.
    if not deals and not featured.get("companies"):
        print("No active deals and no Featured Sector matches — skipping email.")
        return
    today = date.today().strftime("%b %d")
    subject = f"PEHero Daily Deals — {today} — {len(deals)} actionable opportunities"

    if args.dry_run:
        html_body = _render_html(deals, news, unsubscribe_url=f"{SERVICE_URL}/auth/unsubscribe/EXAMPLE_TOKEN", featured=featured)
        text_body = _render_text(deals, news, unsubscribe_url=f"{SERVICE_URL}/auth/unsubscribe/EXAMPLE_TOKEN", featured=featured)
        print(html_body)
        print("\n--- TEXT ---\n")
        print(text_body)
        return

    if args.to:
        html_body = _render_html(deals, news, featured=featured)
        text_body = _render_text(deals, news, featured=featured)
        result = send_email(to=args.to, subject=subject, html_body=html_body, text_body=text_body)
        print(f"Sent to {args.to} — MessageID: {result.get('MessageID', 'n/a')}")
    else:
        sent = send_to_all_users(deals, news, featured=featured)
        print(f"Sent daily deals to {sent} users")


if __name__ == "__main__":
    main()
