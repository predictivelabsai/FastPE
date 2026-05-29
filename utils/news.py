"""RSS news feed fetcher for the right-pane news panel.

Fetches from PE-relevant financial sources (FT, Bloomberg, WSJ, Reuters,
BBC Business) plus Baltic regional sources, returning a unified list of
articles sorted by publish date.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from time import mktime

import feedparser

log = logging.getLogger(__name__)

FEEDS: list[dict] = [
    # Global financial
    {"name": "Financial Times",  "url": "https://www.ft.com/rss/home",                       "lang": "en", "icon": "FT"},
    {"name": "Wall Street Journal", "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml",    "lang": "en", "icon": "WSJ"},
    {"name": "Bloomberg",        "url": "https://feeds.bloomberg.com/markets/news.rss",       "lang": "en", "icon": "BBG"},
    {"name": "Reuters Business", "url": "https://www.reutersagency.com/feed/?taxonomy=best-sectors&post_type=best", "lang": "en", "icon": "RTR"},
    {"name": "BBC Business",     "url": "http://feeds.bbci.co.uk/news/business/rss.xml",      "lang": "en", "icon": "BBC"},
    # Baltic
    {"name": "ERR News",         "url": "https://news.err.ee/rss",                            "lang": "en", "icon": "ERR"},
    {"name": "Baltic Times",     "url": "https://www.baltictimes.com/rss.xml",                "lang": "en", "icon": "BT"},
]

_cache: dict = {"articles": [], "fetched_at": None}
CACHE_TTL = 300  # 5 minutes


def _parse_date(entry) -> datetime:
    for field in ("published_parsed", "updated_parsed"):
        val = getattr(entry, field, None) or entry.get(field)
        if val:
            try:
                return datetime.fromtimestamp(mktime(val), tz=timezone.utc)
            except Exception:
                pass
    return datetime.now(tz=timezone.utc)


def _extract_image(entry) -> str | None:
    for media in getattr(entry, "media_thumbnail", []):
        if "url" in media:
            return media["url"]
    for media in getattr(entry, "media_content", []):
        if "url" in media:
            return media["url"]
    for enc in getattr(entry, "enclosures", []):
        if enc.get("type", "").startswith("image/"):
            return enc.get("href") or enc.get("url")
    return None


def _fetch_one(feed: dict) -> list[dict]:
    try:
        parsed = feedparser.parse(feed["url"])
    except Exception as e:
        log.warning("RSS fetch failed for %s: %s", feed["name"], e)
        return []

    articles = []
    for entry in parsed.entries[:10]:
        url = entry.get("link", "").strip()
        if not url:
            continue
        summary = entry.get("summary", "")
        if summary and len(summary) > 300:
            summary = summary[:297] + "..."
        articles.append({
            "title": entry.get("title", "Untitled").strip(),
            "url": url,
            "summary": summary.strip(),
            "source": feed["name"],
            "icon": feed["icon"],
            "published": _parse_date(entry).isoformat(),
            "image": _extract_image(entry),
        })
    return articles


async def fetch_news() -> list[dict]:
    """Fetch all RSS feeds and return merged, deduplicated, sorted list."""
    now = datetime.now(tz=timezone.utc)
    if _cache["fetched_at"] and (now - _cache["fetched_at"]).total_seconds() < CACHE_TTL:
        return _cache["articles"]

    results = await asyncio.gather(
        *[asyncio.to_thread(_fetch_one, f) for f in FEEDS],
        return_exceptions=True,
    )

    all_articles = []
    seen_urls: set[str] = set()
    for result in results:
        if isinstance(result, Exception):
            log.warning("RSS feed error: %s", result)
            continue
        for article in result:
            if article["url"] not in seen_urls:
                seen_urls.add(article["url"])
                all_articles.append(article)

    all_articles.sort(key=lambda a: a["published"], reverse=True)
    all_articles = all_articles[:50]

    _cache["articles"] = all_articles
    _cache["fetched_at"] = now
    log.info("Fetched %d news articles from %d feeds", len(all_articles), len(FEEDS))
    return all_articles


async def fetch_news_translated(lang: str = "en") -> list[dict]:
    """Fetch news and translate titles if lang != en."""
    articles = await fetch_news()
    if lang == "en" or not articles:
        return articles

    cache_key = f"translated_{lang}"
    if _cache.get(cache_key) and _cache.get("fetched_at") == _cache.get(f"{cache_key}_at"):
        return _cache[cache_key]

    from utils.i18n import LANGUAGES
    lang_name = LANGUAGES.get(lang, {}).get("name", "English")

    try:
        from utils.llm import default_llm
        llm = default_llm()
        titles = [a["title"] for a in articles[:30]]
        prompt = (
            f"Translate these news headlines to {lang_name}. "
            f"Return ONLY the translations, one per line, in the same order. "
            f"Keep proper nouns, company names, and acronyms unchanged.\n\n"
            + "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles))
        )
        result = await asyncio.to_thread(llm.invoke, prompt)
        translated_lines = [l.strip() for l in result.content.strip().split("\n") if l.strip()]
        cleaned = []
        for line in translated_lines:
            import re
            cleaned.append(re.sub(r"^\d+\.\s*", "", line))

        translated = []
        for i, a in enumerate(articles):
            copy = dict(a)
            if i < len(cleaned) and cleaned[i]:
                copy["title"] = cleaned[i]
            translated.append(copy)

        _cache[cache_key] = translated
        _cache[f"{cache_key}_at"] = _cache["fetched_at"]
        return translated
    except Exception as e:
        log.warning("Title translation failed: %s", e)
        return articles
