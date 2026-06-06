"""Entrypoint. Kept as a thin shim so standard runners (`python main.py`)
work without changes. All routing lives in app.py."""

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from utils.logging import setup_logging

setup_logging()

from app import app, serve  # noqa: E402,F401
from utils.config import settings

log = logging.getLogger("scheduler")

EET = ZoneInfo("Europe/Tallinn")


def _prefetch_news():
    """Warm the RSS cache before accepting requests."""
    from utils.news import fetch_news
    try:
        asyncio.run(fetch_news())
    except Exception:
        pass


def _daily_deals_loop():
    """Send daily deals digest at 08:00 EET. Runs as a daemon thread."""
    s = settings()
    if not s.postmark_api_token or not s.daily_deals_to_email:
        log.info("Daily deals scheduler disabled (no POSTMARK_API_TOKEN or DAILY_DEALS_TO_EMAIL)")
        return

    target_hour, target_minute = 8, 0
    log.info("Daily deals scheduler started — target %02d:%02d EET to %s",
             target_hour, target_minute, s.daily_deals_to_email)

    while True:
        now = datetime.now(EET)
        target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        wait_secs = (target - now).total_seconds()
        log.info("Next daily deals email at %s (in %.0f min)", target.isoformat(), wait_secs / 60)
        time.sleep(wait_secs)

        try:
            from scripts.daily_deals import _top_deals, _render_html, _render_text, _fetch_news_sync
            from utils.email import send_email
            from datetime import date

            deals = _top_deals(5)
            if not deals:
                log.warning("No active deals — skipping daily email")
                continue

            news = _fetch_news_sync(5)
            today = date.today().strftime("%b %d")
            subject = f"PEHero Daily Deals — {today} — {len(deals)} actionable opportunities"
            result = send_email(
                to=s.daily_deals_to_email,
                subject=subject,
                html_body=_render_html(deals, news),
                text_body=_render_text(deals, news),
            )
            log.info("Daily deals sent — MessageID: %s", result.get("MessageID"))
        except Exception:
            log.exception("Daily deals email failed")


_t = threading.Thread(target=_prefetch_news, daemon=True)
_t.start()
_t.join(timeout=8)

_deals_t = threading.Thread(target=_daily_deals_loop, daemon=True, name="daily-deals")
_deals_t.start()

if __name__ == "__main__":
    serve(port=settings().port)
