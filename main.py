"""Entrypoint. Kept as a thin shim so standard runners (`python main.py`)
work without changes. All routing lives in app.py."""

import asyncio
import threading

from utils.logging import setup_logging

setup_logging()

from app import app, serve  # noqa: E402,F401
from utils.config import settings


def _prefetch_news():
    """Warm the RSS cache before accepting requests."""
    from utils.news import fetch_news
    try:
        asyncio.run(fetch_news())
    except Exception:
        pass

_t = threading.Thread(target=_prefetch_news, daemon=True)
_t.start()
_t.join(timeout=8)

if __name__ == "__main__":
    serve(port=settings().port)
