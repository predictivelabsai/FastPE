"""Capture Lithuanian product tour screenshots → screenshots/*_lt.png.

Switches the app to Lithuanian, then takes chat + product screenshots
with real Lithuanian company questions.

Usage:
    # server already running on :5058
    python -m scripts.capture_screenshots_lt
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

log = logging.getLogger("capture_lt")

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "screenshots"

BASE_URL = os.environ.get("PEHERO_URL", "http://localhost:5058")
VIEWPORT = {"width": 1400, "height": 900}

TOUR = [
    # (filename, url, wait_selector, full_page, post_action)
    ("01-home-full_lt.png",          "/",                       "text=PEHero",                  True,  None),
    ("02-agents-full_lt.png",        "/agents",                 "text=PEHero",                  True,  None),
    ("03-pricing-full_lt.png",       "/pricing",                "text=PEHero",                  True,  None),
    # Chat screens
    ("04-chat-empty_lt.png",         "/app",                    "#chat-input",                  False, None),
    ("05-chat-triage_lt.png",        "/app",                    "#chat-input",                  False, "triage"),
    ("06-chat-ltm_lt.png",           "/app",                    "#chat-input",                  False, "ltm"),
    ("07-chat-memo_lt.png",          "/app",                    "#chat-input",                  False, "memo"),
    # Pipeline
    ("08-pipeline-kanban_lt.png",    "/app/pipeline",           ".kanban-board",                False, None),
    ("09-pipeline-deal_lt.png",      "/app/pipeline",           ".kanban-board",                False, "first_deal"),
    # Analytics
    ("10-analytics-empty_lt.png",    "/app/analytics",          "#analytics-q",                 False, None),
    ("11-analytics-revenue_lt.png",  "/app/analytics",          "#analytics-q",                 False, "revenue"),
    # Instructions
    ("12-instructions-list_lt.png",  "/app/instructions",       ".instr-list",                  False, None),
]

CHAT_MSGS = {
    "triage": "triage: DR VET veterinarijos klinika, €3,8M pajamos, 76 darbuotojai, Vilnius",
    "ltm":    "ltm: kokie yra DR VET finansiniai rodikliai?",
    "memo":   "memo: parašykite IC memo Kardiolita",
}

ANALYTICS_QUERIES = {
    "revenue": "Top 10 įmonių pagal pajamas, rodyti sektorių",
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


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    SHOTS.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
        page = ctx.new_page()

        # Switch to Lithuanian by setting the lang cookie + hitting /set-lang/lt
        page.goto(BASE_URL + "/set-lang/lt", wait_until="networkidle", timeout=15_000)
        time.sleep(1)

        for fname, path, wait_for, full_page, action in TOUR:
            url = BASE_URL + path
            log.info("→ %s (%s)", url, fname)
            try:
                page.goto(url, wait_until="networkidle", timeout=30_000)
            except Exception as e:
                log.warning("goto failed %s: %s — retrying", url, e)
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
            log.info("  saved %s", out.name)

        browser.close()
    log.info("done — %d Lithuanian frames in %s", len(TOUR), SHOTS)


if __name__ == "__main__":
    main()
