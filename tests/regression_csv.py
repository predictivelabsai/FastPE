"""CSV-driven regression suite — runs test-cases/regression.csv through agents.

Saves results to test-results/<id>.json. Hits the real LLM.

Usage:
    python -m tests.regression_csv                    # all cases
    python -m tests.regression_csv --id tc01          # single case
    python -m tests.regression_csv --dry-run          # route-only, no LLM
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from agents.base import cached_agent
from agents.registry import AGENTS_BY_SLUG
from agents import router as agent_router

log = logging.getLogger(__name__)

CASES_PATH = Path(__file__).resolve().parent.parent / "test-cases" / "regression.csv"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "test-results"


def _load_cases(filter_id: str | None = None) -> list[dict]:
    cases = []
    with open(CASES_PATH) as f:
        for row in csv.DictReader(f):
            if filter_id and row["id"] != filter_id:
                continue
            cases.append(row)
    return cases


def _run_case(case: dict, timeout: int = 90) -> dict:
    """Run a single test case through the agent and return the result."""
    tc_id = case["id"]
    prompt = case["prompt"]
    expected_agent = case.get("expect_agent", "")
    expected_text = case.get("expect_contains", "")

    result = {
        "id": tc_id,
        "prompt": prompt,
        "expected_agent": expected_agent,
        "expected_contains": expected_text,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Step 1: Route
    routed_slug = agent_router.route(prompt)
    result["routed_agent"] = routed_slug
    result["route_match"] = routed_slug == expected_agent

    # Step 2: Invoke agent
    try:
        start = time.time()
        graph = cached_agent(routed_slug)

        from langchain_core.messages import HumanMessage, SystemMessage

        currency_directive = (
            "[Session preferences] Reporting currency: EUR (€). "
            "Format all monetary figures in EUR unless the user explicitly overrides."
        )
        stripped = agent_router.strip_prefix(prompt)
        messages = [SystemMessage(content=currency_directive), HumanMessage(content=stripped)]

        lc_result = graph.invoke({"messages": messages})

        elapsed = round(time.time() - start, 1)
        result["elapsed_s"] = elapsed

        # Extract final text
        msgs = lc_result.get("messages", [])
        tools_called = []
        final_text = ""
        for m in msgs:
            if hasattr(m, "tool_calls") and m.tool_calls:
                tools_called.extend(tc["name"] for tc in m.tool_calls)
            if hasattr(m, "content") and m.content:
                final_text = m.content

        result["response"] = final_text[:2000]
        result["response_length"] = len(final_text)
        result["tools_called"] = tools_called

        # Step 3: Check assertions
        contains_match = expected_text.lower() in final_text.lower() if expected_text else True
        result["contains_match"] = contains_match
        result["passed"] = result["route_match"] and contains_match
        result["error"] = None

    except Exception as e:
        result["error"] = str(e)
        result["passed"] = False
        result["elapsed_s"] = 0
        result["response"] = ""
        result["tools_called"] = []
        log.error("  FAIL %s: %s", tc_id, e)

    return result


def _run_case_dry(case: dict) -> dict:
    """Route-only dry run — no LLM call."""
    tc_id = case["id"]
    prompt = case["prompt"]
    expected_agent = case.get("expect_agent", "")

    routed_slug = agent_router.route(prompt)
    passed = routed_slug == expected_agent

    return {
        "id": tc_id,
        "prompt": prompt,
        "expected_agent": expected_agent,
        "routed_agent": routed_slug,
        "route_match": passed,
        "passed": passed,
        "dry_run": True,
    }


def run(filter_id: str | None = None, dry_run: bool = False, timeout: int = 90):
    cases = _load_cases(filter_id)
    if not cases:
        log.error("No test cases found" + (f" matching id={filter_id}" if filter_id else ""))
        return

    log.info("Running %d test cases%s", len(cases), " (dry-run)" if dry_run else "")
    RESULTS_DIR.mkdir(exist_ok=True)

    results = []
    passed = 0
    failed = 0

    for case in cases:
        tc_id = case["id"]
        log.info("  [%s] %s ...", tc_id, case["prompt"][:60])

        if dry_run:
            result = _run_case_dry(case)
        else:
            result = _run_case(case, timeout=timeout)

        # Save individual result
        result_path = RESULTS_DIR / f"{tc_id}.json"
        result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

        if result["passed"]:
            passed += 1
            log.info("    PASS (%s)", result.get("routed_agent", "?"))
        else:
            failed += 1
            log.warning("    FAIL — routed=%s expected=%s contains=%s",
                        result.get("routed_agent"), result.get("expected_agent"),
                        result.get("contains_match", "?"))

        results.append(result)

    # Summary
    log.info("")
    log.info("Results: %d/%d passed, %d failed", passed, len(cases), failed)

    # Write summary JSON
    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "total": len(cases),
        "passed": passed,
        "failed": failed,
        "dry_run": dry_run,
        "cases": [{
            "id": r["id"],
            "passed": r["passed"],
            "routed": r.get("routed_agent"),
            "expected": r.get("expected_agent"),
            "elapsed": r.get("elapsed_s"),
        } for r in results],
    }
    (RESULTS_DIR / "summary.json").write_text(json.dumps(summary, indent=2))

    return failed == 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", help="Run a single test case by ID")
    ap.add_argument("--dry-run", action="store_true", help="Route-only, no LLM calls")
    ap.add_argument("--timeout", type=int, default=90, help="Per-case timeout (seconds)")
    args = ap.parse_args()
    ok = run(filter_id=args.id, dry_run=args.dry_run, timeout=args.timeout)
    sys.exit(0 if ok else 1)
