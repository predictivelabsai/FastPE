"""Capture a tour of the PEHero app into ./screenshots.

The script drives a real browser via Playwright against a locally-running
PEHero server (default http://localhost:5058). It produces a deterministic
set of frames for `make_gif.py` and `make_pdf.py`.

Usage:
    # server already running on :5058
    python -m scripts.capture_screenshots
"""

from __future__ import annotations

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
    ("01-home-full.png",          "/",                       "text=22 specialist agents",    True,  None),
    ("02-platform-full.png",      "/platform",               "text=One system. Every stage", True,  None),
    ("03-agents-full.png",        "/agents",                 "text=Every role already",      True,  None),
    ("04-agent-detail-triage.png","/agents/deal_triage",     "text=Deal Triage Agent",       True,  None),
    ("05-how-it-works-full.png",  "/how-it-works",           "text=From teaser to signed",   True,  None),
    ("06-pricing-full.png",       "/pricing",                "text=Start with synthetic",    True,  None),
    # Product screens
    ("07-chat-empty.png",         "/app",                    "#chat-input",                  False, None),
    ("08-chat-triage.png",        "/app",                    "#chat-input",                  False, "triage"),
    ("09-chat-lbo.png",           "/app",                    "#chat-input",                  False, "lbo"),
    ("10-chat-memo.png",          "/app",                    "#chat-input",                  False, "memo"),
    # Pipeline (kanban + deal detail)
    ("11-pipeline-kanban.png",    "/app/pipeline",           ".kanban-board",                False, None),
    ("12-pipeline-software.png",  "/app/pipeline?sector=software", ".kanban-board",          False, None),
    # Deal detail is captured via "first-card" action
    ("13-pipeline-deal.png",      "/app/pipeline",           ".kanban-board",                False, "first_deal"),
    # Analytics
    ("14-analytics-empty.png",    "/app/analytics",          "#analytics-q",                 False, None),
    ("15-analytics-stages.png",   "/app/analytics",          "#analytics-q",                 False, "stages"),
    ("16-analytics-sector.png",   "/app/analytics",          "#analytics-q",                 False, "ev_by_sector"),
    # Instructions
    ("17-instructions-list.png",  "/app/instructions",       ".instr-list",                  False, None),
    ("18-instructions-edit.png",  "/app/instructions/deal_triage", ".instr-textarea",        False, None),
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
    # wait for agent_route + at least one assistant bubble with text
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
    time.sleep(0.5)  # let artifact pane paint


def _run_analytics(page, question: str) -> None:
    page.fill("#analytics-q", question)
    page.evaluate("() => runAnalytics()")
    # wait until the result card has been populated
    page.wait_for_function(
        """() => {
            const r = document.getElementById('analytics-result');
            if (!r) return false;
            return r.querySelector('.analytics-chart svg, .analytics-chart .plotly, .analytics-error') !== null;
        }""",
        timeout=60_000,
    )
    time.sleep(1.0)  # let plotly finish


def _click_first_deal(page) -> None:
    """On /app/pipeline, click the first deal card and wait for the deal detail to load."""
    page.wait_for_selector(".deal-card-link")
    first_href = page.eval_on_selector(".deal-card-link", "el => el.getAttribute('href')")
    page.goto(BASE_URL + first_href, wait_until="networkidle", timeout=30_000)
    page.wait_for_selector(".deal-brief", timeout=10_000)
    time.sleep(0.5)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    SHOTS.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
        page = ctx.new_page()

        for fname, path, wait_for, full_page, action in TOUR:
            url = BASE_URL + path
            log.info("→ %s", url)
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
                time.sleep(0.4)

            out = SHOTS / fname
            page.screenshot(path=str(out), full_page=full_page)
            log.info("  saved %s", out.relative_to(ROOT))

        browser.close()
    log.info("done — %d frames in %s", len(TOUR), SHOTS)


if __name__ == "__main__":
    main()
