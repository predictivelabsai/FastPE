"""Capture a tour of the PEHero app into ./screenshots.

The script drives a real browser via Playwright against a locally-running
PEHero server (default http://localhost:5058). It produces a deterministic
set of frames for `make_gif.py` and `make_pdf.py`.

Usage:
    # server already running on :5058
    python -m scripts.capture_screenshots                # English
    python -m scripts.capture_screenshots --lang lt      # Lithuanian
    python -m scripts.capture_screenshots --lang all     # Both EN + LT
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

log = logging.getLogger("capture")

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "screenshots"

BASE_URL = os.environ.get("PEHERO_URL", "http://localhost:5058")
VIEWPORT = {"width": 1400, "height": 900}


TOUR = [
    # (filename, url, wait_selector, full_page, post_action)
    ("01-home-full.png",          "/",                       "text=specialist agents",       True,  None),
    ("02-platform-full.png",      "/platform",               "text=One system",              True,  None),
    ("03-agents-full.png",        "/agents",                 "text=Every role",              True,  None),
    ("04-agent-detail-triage.png","/agents/deal_triage",     "text=Deal Triage",             True,  None),
    ("05-how-it-works-full.png",  "/how-it-works",           "text=From teaser",             True,  None),
    ("06-pricing-full.png",       "/pricing",                "text=Start with",              True,  None),
    # Product screens
    ("07-chat-empty.png",         "/app",                    "#chat-input",                  False, None),
    ("08-chat-triage.png",        "/app",                    "#chat-input",                  False, "triage"),
    ("09-chat-lbo.png",           "/app",                    "#chat-input",                  False, "lbo"),
    ("10-chat-memo.png",          "/app",                    "#chat-input",                  False, "memo"),
    # News pane
    ("11-chat-news.png",          "/app",                    "#chat-input",                  False, "news"),
    # Pipeline (kanban + deal detail)
    ("12-pipeline-kanban.png",    "/app/pipeline",           ".kanban-board",                False, None),
    ("13-pipeline-deal.png",      "/app/pipeline",           ".kanban-board",                False, "first_deal"),
    # Company search
    ("14-companies.png",          "/app/companies",          ".search-table",                False, None),
    ("15-companies-health.png",   "/app/companies?sector=healthcare", ".search-table",       False, None),
    # Analytics
    ("16-analytics-empty.png",    "/app/analytics",          "#analytics-q",                 False, None),
    ("17-analytics-stages.png",   "/app/analytics",          "#analytics-q",                 False, "stages"),
    ("18-analytics-sector.png",   "/app/analytics",          "#analytics-q",                 False, "ev_by_sector"),
    # Instructions
    ("19-instructions-list.png",  "/app/instructions",       ".instr-list",                  False, None),
    ("20-instructions-edit.png",  "/app/instructions/deal_triage", ".instr-textarea",        False, None),
]


CHAT_MSGS = {
    "triage":   "triage: DR VET veterinary clinic, €3.8M revenue, 76 employees, Vilnius",
    "lbo":      "lbo: build a 5-year model for Kardiolita at 12% rev growth, 300bps margin exp",
    "memo":     "memo: draft the IC memo for Kardiolita",
}

ANALYTICS_QUERIES = {
    "stages":       "Company count by deal stage",
    "ev_by_sector": "Average EBITDA margin by sector",
}


def _run_chat(page, msg: str) -> None:
    page.fill("#chat-input", msg)
    page.evaluate(
        "() => document.querySelector('#chat-form').dispatchEvent("
        "new Event('submit', {cancelable: true}))"
    )
    page.wait_for_function(
        """() => {
            const m = document.querySelector('#messages');
            if (!m) return false;
            const bubbles = m.querySelectorAll('.msg-assistant .msg-bubble');
            if (!bubbles.length) return false;
            const last = bubbles[bubbles.length-1];
            return last && (last.textContent||'').length > 120
                   && !last.parentElement.classList.contains('streaming');
        }""",
        timeout=120_000,
    )
    time.sleep(0.5)


def _open_news_pane(page) -> None:
    page.wait_for_selector("#news-btn", timeout=5_000)
    page.click("#news-btn")
    page.wait_for_function(
        "() => document.querySelector('#news-body') && "
        "document.querySelector('#news-body').style.display !== 'none'",
        timeout=15_000,
    )
    time.sleep(1.0)


def _run_analytics(page, question: str) -> None:
    page.fill("#analytics-q", question)
    page.evaluate("() => runAnalytics()")
    page.wait_for_function(
        """() => {
            const r = document.getElementById('analytics-result');
            if (!r) return false;
            return r.querySelector('.analytics-chart svg, .analytics-chart .plotly, .analytics-error') !== null;
        }""",
        timeout=60_000,
    )
    time.sleep(1.0)


def _click_first_deal(page) -> None:
    page.wait_for_selector(".deal-card-link")
    first_href = page.eval_on_selector(".deal-card-link", "el => el.getAttribute('href')")
    page.goto(BASE_URL + first_href, wait_until="networkidle", timeout=30_000)
    page.wait_for_selector(".deal-brief", timeout=10_000)
    time.sleep(0.5)


def _set_language(page, lang: str) -> None:
    page.evaluate(f"""async () => {{
        await fetch('/app/config', {{
            method: 'POST',
            body: new URLSearchParams({{ lang: '{lang}' }}),
        }});
    }}""")
    time.sleep(0.3)


def capture_tour(lang: str = "en") -> None:
    suffix = f"-{lang}" if lang != "en" else ""
    outdir = SHOTS if lang == "en" else SHOTS / lang
    outdir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
        page = ctx.new_page()

        # Set language via session
        if lang != "en":
            page.goto(BASE_URL + "/app", wait_until="networkidle", timeout=30_000)
            _set_language(page, lang)

        for fname, path, wait_for, full_page, action in TOUR:
            url = BASE_URL + path
            log.info("[%s] → %s", lang, url)
            try:
                page.goto(url, wait_until="networkidle", timeout=30_000)
            except Exception as e:
                log.warning("goto failed %s: %s — retrying with 'load'", url, e)
                page.goto(url, wait_until="load", timeout=30_000)

            if wait_for:
                try:
                    page.wait_for_selector(wait_for, timeout=10_000)
                except Exception:
                    log.warning("selector %r didn't appear on %s", wait_for, path)

            if action:
                if action in CHAT_MSGS:
                    _run_chat(page, CHAT_MSGS[action])
                elif action in ANALYTICS_QUERIES:
                    _run_analytics(page, ANALYTICS_QUERIES[action])
                elif action == "first_deal":
                    _click_first_deal(page)
                elif action == "news":
                    _open_news_pane(page)
                time.sleep(0.4)

            out = outdir / fname
            page.screenshot(path=str(out), full_page=full_page)
            log.info("  saved %s", out.relative_to(ROOT))

        browser.close()
    log.info("[%s] done — %d frames in %s", lang, len(TOUR), outdir)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", default="en", help="Language code: en, lt, et, fi, sv, or 'all' for en+lt")
    args = parser.parse_args()

    if args.lang == "all":
        capture_tour("en")
        capture_tour("lt")
    else:
        capture_tour(args.lang)


if __name__ == "__main__":
    main()
