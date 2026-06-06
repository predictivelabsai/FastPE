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
    """Send daily deals digest at 08:00 EET to all opted-in users."""
    s = settings()
    if not s.postmark_api_token:
        log.info("Daily deals scheduler disabled (no POSTMARK_API_TOKEN)")
        return

    target_hour, target_minute = 8, 0
    log.info("Daily deals scheduler started — target %02d:%02d EET to opted-in users",
             target_hour, target_minute)

    while True:
        now = datetime.now(EET)
        target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        wait_secs = (target - now).total_seconds()
        log.info("Next daily deals email at %s (in %.0f min)", target.isoformat(), wait_secs / 60)
        time.sleep(wait_secs)

        try:
            from scripts.daily_deals import _top_deals, _fetch_news_sync, send_to_all_users

            deals = _top_deals(5)
            if not deals:
                log.warning("No active deals — skipping daily email")
                continue

            news = _fetch_news_sync(5)
            sent = send_to_all_users(deals, news)
            log.info("Daily deals loop complete — sent to %d users", sent)
        except Exception:
            log.exception("Daily deals email failed")


_t = threading.Thread(target=_prefetch_news, daemon=True)
_t.start()
_t.join(timeout=8)

_deals_t = threading.Thread(target=_daily_deals_loop, daemon=True, name="daily-deals")
_deals_t.start()

if __name__ == "__main__":
    serve(port=settings().port)
