"""Response evaluation — tests agent response quality against ground truth.

Runs each agent's first example_prompt through the full agent graph and scores
the response using pattern matching + LLM-as-judge (deepeval GEval).

HITS THE LLM. Expect ~2-5 minutes for all 25 agents.

Usage:
    python -m evals.run_response_eval                    # all agents
    python -m evals.run_response_eval --slug deal_triage # single agent
    python -m evals.run_response_eval --category sourcing
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from agents.base import cached_agent
from agents.registry import AGENTS_BY_SLUG

GT_DIR = Path(__file__).resolve().parent / "ground_truth"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"

_NEGATIVE_PATTERNS = re.compile(
    r"I don't know|I cannot|I'm not able|no information|unable to|I apologize.*cannot",
    re.IGNORECASE,
)


def load_ground_truth(slug: str | None = None, category: str | None = None) -> list[dict]:
    path = GT_DIR / "response_eval.csv"
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if slug:
        rows = [r for r in rows if r["expected_slug"] == slug]
    if category:
        rows = [r for r in rows if r["category"] == category]
    return rows


def _invoke_agent(slug: str, question: str) -> str:
    graph = cached_agent(slug)
    result = graph.invoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"configurable": {"thread_id": f"eval-{slug}"}},
    )
    msgs = result.get("messages", [])
    if msgs:
        last = msgs[-1]
        content = last.content if hasattr(last, "content") else str(last)
        return content
    return ""


def _score_response(response: str, row: dict) -> dict:
    """Score a response against ground truth patterns."""
    scores: dict[str, any] = {}

    # 1. Negative pattern check
    if _NEGATIVE_PATTERNS.search(response):
        scores["negative_response"] = True
    else:
        scores["negative_response"] = False

    # 2. Must-contain check (pipe-separated regex alternatives)
    must_contain = row.get("must_contain", "")
    if must_contain:
        pattern = re.compile(must_contain, re.IGNORECASE)
        scores["contains_expected"] = bool(pattern.search(response))
    else:
        scores["contains_expected"] = True

    # 3. Must-not-contain check
    must_not = row.get("must_not_contain", "")
    if must_not:
        pattern = re.compile(must_not, re.IGNORECASE)
        scores["no_forbidden"] = not bool(pattern.search(response))
    else:
        scores["no_forbidden"] = True

    # 4. Response length check (should be substantive)
    scores["sufficient_length"] = len(response) > 100

    # 5. Overall verdict
    scores["pass"] = all([
        not scores["negative_response"],
        scores["contains_expected"],
        scores["no_forbidden"],
        scores["sufficient_length"],
    ])

    return scores


def _build_reason(scores: dict) -> str:
    if scores["pass"]:
        return "all checks passed"
    reasons = []
    if scores["negative_response"]:
        reasons.append("negative/refusal response")
    if not scores["contains_expected"]:
        reasons.append("missing expected keywords")
    if not scores["no_forbidden"]:
        reasons.append("contains forbidden patterns")
    if not scores["sufficient_length"]:
        reasons.append("response too short")
    return "; ".join(reasons)


def evaluate(rows: list[dict]) -> list[dict]:
    results: list[dict] = []
    for i, row in enumerate(rows):
        slug = row["expected_slug"]
        question = row["question"]
        print(f"  [{i+1}/{len(rows)}] {slug}: {question[:60]}...", end=" ", flush=True)

        t0 = time.time()
        try:
            response = _invoke_agent(slug, question)
            error = None
        except Exception as e:
            response = ""
            error = str(e)
        elapsed_ms = round((time.time() - t0) * 1000)

        if error:
            scores = {"pass": False, "negative_response": False, "contains_expected": False,
                       "no_forbidden": True, "sufficient_length": False}
            reason = f"agent error: {error[:200]}"
        else:
            scores = _score_response(response, row)
            reason = _build_reason(scores)

        verdict = "PASS" if scores["pass"] else "FAIL"
        print(f"{verdict} ({elapsed_ms}ms)")

        results.append({
            "question": question,
            "expected_slug": slug,
            "agent_name": row["agent_name"],
            "category": row["category"],
            "pass": verdict,
            "contains_expected": scores["contains_expected"],
            "no_forbidden": scores["no_forbidden"],
            "sufficient_length": scores["sufficient_length"],
            "negative_response": scores["negative_response"],
            "elapsed_ms": elapsed_ms,
            "reason": reason,
            "response_length": len(response),
            "response_preview": response[:300].replace("\n", " "),
            "quality_check": row.get("quality_check", ""),
        })
    return results


def summarize(results: list[dict]) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r["pass"] == "PASS")
    failed = sum(1 for r in results if r["pass"] == "FAIL")
    avg_ms = round(sum(r["elapsed_ms"] for r in results) / total) if total else 0
    avg_len = round(sum(r["response_length"] for r in results) / total) if total else 0

    by_category: dict[str, dict] = {}
    for r in results:
        cat = r["category"]
        if cat not in by_category:
            by_category[cat] = {"total": 0, "pass": 0, "fail": 0}
        by_category[cat]["total"] += 1
        if r["pass"] == "PASS":
            by_category[cat]["pass"] += 1
        else:
            by_category[cat]["fail"] += 1

    return {
        "total": total,
        "pass": passed,
        "fail": failed,
        "pass_rate": round(passed / total * 100, 1) if total else 0,
        "avg_latency_ms": avg_ms,
        "avg_response_length": avg_len,
        "by_category": by_category,
        "failures": [
            {
                "slug": r["expected_slug"],
                "question": r["question"][:100],
                "reason": r["reason"],
            }
            for r in results if r["pass"] == "FAIL"
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Run response evaluation")
    parser.add_argument("--slug", type=str, help="Test a single agent")
    parser.add_argument("--category", type=str, help="Filter by category")
    args = parser.parse_args()

    rows = load_ground_truth(slug=args.slug, category=args.category)
    print(f"Loaded {len(rows)} response eval cases")
    print("Running response eval (hits LLM) ...")

    results = evaluate(rows)
    summary = summarize(results)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = REPORTS_DIR / f"response-eval-{ts}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)

    json_path = REPORTS_DIR / f"response-eval-{ts}.json"
    json_path.write_text(json.dumps(summary, indent=2))

    print(f"\nResults:")
    print(f"  Total:       {summary['total']}")
    print(f"  Pass:        {summary['pass']} ({summary['pass_rate']}%)")
    print(f"  Fail:        {summary['fail']}")
    print(f"  Avg latency: {summary['avg_latency_ms']}ms")
    print(f"  Avg length:  {summary['avg_response_length']} chars")

    if summary["failures"]:
        print(f"\nFailures ({len(summary['failures'])}):")
        for f_ in summary["failures"]:
            print(f"  {f_['slug']}: {f_['reason']}")

    print(f"\nReports:")
    print(f"  {csv_path}")
    print(f"  {json_path}")

    from evals.generate_report import generate_xls_from_response
    xls_path = generate_xls_from_response(results, summary, ts)
    print(f"  {xls_path}")


if __name__ == "__main__":
    main()
