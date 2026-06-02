"""Routing evaluation — tests agent router accuracy against ground truth.

Tests three routing modes:
  1. Prefix routing (deterministic, no LLM)
  2. Keyword routing (deterministic, no LLM)
  3. Free-form routing (uses LLM fallback classifier)

Usage:
    python -m evals.run_routing_eval                 # all cases
    python -m evals.run_routing_eval --no-llm        # prefix + keyword only (fast)
    python -m evals.run_routing_eval --category sourcing  # filter by category
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from agents.registry import AGENTS_BY_SLUG
from agents.router import route

GT_DIR = Path(__file__).resolve().parent / "ground_truth"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def load_ground_truth(category: str | None = None) -> list[dict]:
    path = GT_DIR / "routing_eval.csv"
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if category:
        rows = [r for r in rows if r["category"] == category]
    return rows


def evaluate(rows: list[dict], skip_llm: bool = False) -> list[dict]:
    results: list[dict] = []
    for row in rows:
        if skip_llm and row["route_type"] == "free_form":
            continue

        question = row["question"]
        expected = row["expected_slug"]
        t0 = time.time()
        try:
            actual = route(question)
        except Exception as e:
            actual = f"ERROR: {e}"
        elapsed_ms = round((time.time() - t0) * 1000)

        passed = actual == expected
        # Accept category-level correct as partial pass
        category_match = False
        if not passed and actual in AGENTS_BY_SLUG and expected in AGENTS_BY_SLUG:
            category_match = (
                AGENTS_BY_SLUG[actual].category == AGENTS_BY_SLUG[expected].category
            )

        results.append({
            "question": question,
            "expected_slug": expected,
            "actual_slug": actual,
            "route_type": row["route_type"],
            "category": row["category"],
            "agent_name": row["agent_name"],
            "pass": "PASS" if passed else "PASS_CATEGORY" if category_match else "FAIL",
            "elapsed_ms": elapsed_ms,
            "reason": (
                "exact match" if passed
                else f"category match (expected {expected}, got {actual})" if category_match
                else f"wrong agent: expected {expected}, got {actual}"
            ),
        })
    return results


def summarize(results: list[dict]) -> dict:
    total = len(results)
    exact = sum(1 for r in results if r["pass"] == "PASS")
    category = sum(1 for r in results if r["pass"] == "PASS_CATEGORY")
    fail = sum(1 for r in results if r["pass"] == "FAIL")

    by_route_type: dict[str, dict] = {}
    for r in results:
        rt = r["route_type"]
        if rt not in by_route_type:
            by_route_type[rt] = {"total": 0, "pass": 0, "category": 0, "fail": 0}
        by_route_type[rt]["total"] += 1
        if r["pass"] == "PASS":
            by_route_type[rt]["pass"] += 1
        elif r["pass"] == "PASS_CATEGORY":
            by_route_type[rt]["category"] += 1
        else:
            by_route_type[rt]["fail"] += 1

    by_category: dict[str, dict] = {}
    for r in results:
        cat = r["category"]
        if cat not in by_category:
            by_category[cat] = {"total": 0, "pass": 0, "fail": 0}
        by_category[cat]["total"] += 1
        if r["pass"] in ("PASS", "PASS_CATEGORY"):
            by_category[cat]["pass"] += 1
        else:
            by_category[cat]["fail"] += 1

    avg_ms = round(sum(r["elapsed_ms"] for r in results) / total) if total else 0

    return {
        "total": total,
        "exact_pass": exact,
        "category_pass": category,
        "fail": fail,
        "exact_rate": round(exact / total * 100, 1) if total else 0,
        "effective_rate": round((exact + category) / total * 100, 1) if total else 0,
        "avg_latency_ms": avg_ms,
        "by_route_type": by_route_type,
        "by_category": by_category,
        "failures": [
            {"question": r["question"], "expected": r["expected_slug"], "actual": r["actual_slug"]}
            for r in results if r["pass"] == "FAIL"
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Run routing evaluation")
    parser.add_argument("--no-llm", action="store_true", help="Skip free-form (LLM) cases")
    parser.add_argument("--category", type=str, help="Filter by agent category")
    args = parser.parse_args()

    rows = load_ground_truth(category=args.category)
    print(f"Loaded {len(rows)} ground truth cases")
    if args.no_llm:
        rows = [r for r in rows if r["route_type"] != "free_form"]
        print(f"  (filtered to {len(rows)} non-LLM cases)")

    print("Running routing eval ...")
    results = evaluate(rows, skip_llm=args.no_llm)
    summary = summarize(results)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = REPORTS_DIR / f"routing-eval-{ts}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)

    json_path = REPORTS_DIR / f"routing-eval-{ts}.json"
    json_path.write_text(json.dumps(summary, indent=2))

    print(f"\nResults:")
    print(f"  Total:          {summary['total']}")
    print(f"  Exact pass:     {summary['exact_pass']} ({summary['exact_rate']}%)")
    print(f"  Category pass:  {summary['category_pass']}")
    print(f"  Fail:           {summary['fail']}")
    print(f"  Effective rate:  {summary['effective_rate']}%")
    print(f"  Avg latency:    {summary['avg_latency_ms']}ms")

    if summary["failures"]:
        print(f"\nFailures ({len(summary['failures'])}):")
        for f_ in summary["failures"][:10]:
            print(f"  Q: {f_['question'][:80]}")
            print(f"    expected={f_['expected']}, actual={f_['actual']}")

    print(f"\nReports:")
    print(f"  {csv_path}")
    print(f"  {json_path}")

    from evals.generate_report import generate_xls_from_routing
    xls_path = generate_xls_from_routing(results, summary, ts)
    print(f"  {xls_path}")


if __name__ == "__main__":
    main()
