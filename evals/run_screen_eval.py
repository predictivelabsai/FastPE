"""Screen evaluation — Baltic health, dental & dermatology clinics,
non-institutional ownership, €3-10M revenue.

Scope: human health, dental and dermatology care providers — dental practices,
dermatology / skin clinics, and general / specialist medical clinics. The
clinical verticals and their EMTAK/NACE codes come from the sector-code
taxonomy (``tools/sector_codes.py``); veterinary (animal health) and
non-clinical adjacencies (pharmacy, medical devices, wholesale) are excluded.

Two layers:

1. A DETERMINISTIC DB SCREEN (`screen_db`) that runs the thesis directly against
   `pehero.companies` — the ground-truth universe of targets that actually match
   sector = healthcare, country ∈ {EE, LT, LV}, ownership ∈ {founder, family},
   a health-or-dental sub-sector (excluding veterinary), and revenue in the
   €3-10M band. This needs a migrated + seeded Postgres but NO LLM, and is what
   `--no-llm` runs on its own.

2. An AGENT BEHAVIOURAL EVAL that puts the thesis to the sourcing agents
   (market_scanner / deal_triage / seller_intent) and scores whether each honours
   all four screen dimensions — geography, sub-sector, ownership and the revenue
   band — while also checking overlap with the DB universe. HITS THE LLM + DB.

Mirrors the harness in `run_response_eval.py` (CSV ground truth → evaluate →
summarize → timestamped CSV/JSON/XLS in reports/).

Usage:
    python -m evals.run_screen_eval                 # DB screen + agent eval (LLM)
    python -m evals.run_screen_eval --no-llm        # deterministic DB screen only
    python -m evals.run_screen_eval --slug market_scanner
    python -m evals.run_screen_eval --limit 50      # cap the DB universe
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from agents.base import cached_agent
from tools.sector_codes import build_screen_sql

GT_DIR = Path(__file__).resolve().parent / "ground_truth"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"

# The clinical verticals this thesis screens for — named from the sector-code
# taxonomy (tools/sector_codes.py), which owns the EMTAK/NACE codes, sub_sector
# labels and multilingual keywords behind each. Dermatology resolves to
# specialist medical practice (EMTAK 86220 / NACE 86.22) + skin keywords.
SCREEN_VERTICALS = ("dental", "dermatology", "general_medical",
                    "specialist_medical", "health_clinic")

# ── The thesis, encoded once ─────────────────────────────────────────────
REVENUE_MIN_EUR = 3_000_000
REVENUE_MAX_EUR = 10_000_000
BALTIC = ("EE", "LT", "LV")
NON_INSTITUTIONAL = ("founder", "family")

_NEGATIVE_PATTERNS = re.compile(
    r"I don't know|I cannot|I'm not able|no information|unable to|I apologize.*cannot",
    re.IGNORECASE,
)

# Screen-dimension coverage — a response must address all four to pass.
_CRITERIA = {
    "geography": re.compile(
        r"baltic|eston|latvia|lithuan|tallinn|riga|vilnius|\bEE\b|\bLT\b|\bLV\b", re.I),
    "sub_sector": re.compile(
        r"dental|dentist|dermatolog|skin|clinic|health\s?care|medical|health", re.I),
    "ownership": re.compile(
        r"founder|family|non[-\s]?institutional|owner[-\s]?operated|independent|"
        r"privately[-\s]?held|closely[-\s]?held", re.I),
    "revenue_band": re.compile(
        r"3\s*[-–to]{1,3}\s*10|€\s?3|€\s?10|\b3\s?m|\b10\s?m|revenue|turnover|EBITDA|"
        r"million|\bEUR\b|€", re.I),
}


# ── Layer 1: deterministic DB screen ─────────────────────────────────────

_SCREEN_TEMPLATE = """
SELECT slug, name, country, hq_city, sector, sub_sector,
       revenue_ltm, ebitda_ltm, ownership, deal_stage
FROM pehero.companies
WHERE sector = 'healthcare'
  AND (UPPER(country) = ANY(%(codes)s)
       OR country ILIKE ANY(ARRAY['%%eston%%','%%latvia%%','%%lithuan%%']))
  AND LOWER(COALESCE(ownership, '')) = ANY(%(ownership)s)
  AND {taxonomy}
  AND revenue_ltm BETWEEN %(rmin)s AND %(rmax)s
ORDER BY revenue_ltm DESC
LIMIT %(limit)s
"""


def screen_db(limit: int = 100) -> dict:
    """Run the thesis directly against the company DB. The clinical-vertical
    filter (dental + dermatology + health/medical clinics, excluding veterinary
    and non-clinical adjacencies) comes from the sector-code taxonomy. Degrades
    gracefully when the DB is unreachable or unseeded."""
    tax_frag, tax_params = build_screen_sql(SCREEN_VERTICALS)
    sql = _SCREEN_TEMPLATE.format(taxonomy=tax_frag)
    try:
        from db import fetch_all
        rows = fetch_all(sql, {
            "codes": list(BALTIC),
            "ownership": list(NON_INSTITUTIONAL),
            "rmin": REVENUE_MIN_EUR,
            "rmax": REVENUE_MAX_EUR,
            "limit": limit,
            **tax_params,
        })
        return {"ok": True, "count": len(rows), "companies": rows, "note": ""}
    except Exception as e:  # noqa: BLE001 — DB is optional for the agent layer
        return {"ok": False, "count": 0, "companies": [],
                "note": f"DB screen unavailable ({str(e)[:160]}). "
                        "Seed Baltic healthcare data (scripts.scrape_ee / load_ee_data) to populate."}


# ── Layer 2: agent behavioural eval ──────────────────────────────────────

def load_ground_truth(slug: str | None = None) -> list[dict]:
    path = GT_DIR / "screen_eval.csv"
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if slug:
        rows = [r for r in rows if r["expected_slug"] == slug]
    return rows


def _invoke_agent(slug: str, question: str) -> str:
    graph = cached_agent(slug)
    result = graph.invoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"configurable": {"thread_id": f"screen-eval-{slug}"}},
    )
    msgs = result.get("messages", [])
    if msgs:
        last = msgs[-1]
        return last.content if hasattr(last, "content") else str(last)
    return ""


def _db_overlap(response: str, universe: list[dict]) -> int:
    """How many DB-universe company names the response actually surfaces."""
    if not universe:
        return 0
    low = response.lower()
    return sum(1 for c in universe if (c.get("name") or "").strip()
              and c["name"].lower() in low)


def _score_response(response: str, row: dict, universe: list[dict]) -> dict:
    scores: dict = {}
    scores["negative_response"] = bool(_NEGATIVE_PATTERNS.search(response))

    # Screen-dimension coverage (the heart of this eval).
    covered = {name: bool(rx.search(response)) for name, rx in _CRITERIA.items()}
    scores.update(covered)
    scores["criteria_covered"] = sum(covered.values())
    scores["all_criteria"] = all(covered.values())

    # Base must/must-not from the CSV, as in run_response_eval.
    must_contain = row.get("must_contain", "")
    scores["contains_expected"] = (
        bool(re.compile(must_contain, re.I).search(response)) if must_contain else True)
    must_not = row.get("must_not_contain", "")
    scores["no_forbidden"] = (
        not bool(re.compile(must_not, re.I).search(response)) if must_not else True)

    scores["sufficient_length"] = len(response) > 100
    scores["db_overlap"] = _db_overlap(response, universe)

    scores["pass"] = all([
        not scores["negative_response"],
        scores["all_criteria"],
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
    if not scores["all_criteria"]:
        missing = [n for n in _CRITERIA if not scores.get(n)]
        reasons.append("missing screen dimension(s): " + ", ".join(missing))
    if not scores["contains_expected"]:
        reasons.append("missing expected keywords")
    if not scores["no_forbidden"]:
        reasons.append("contains forbidden patterns")
    if not scores["sufficient_length"]:
        reasons.append("response too short")
    return "; ".join(reasons)


def evaluate(rows: list[dict], universe: list[dict]) -> list[dict]:
    results: list[dict] = []
    for i, row in enumerate(rows):
        slug = row["expected_slug"]
        question = row["question"]
        print(f"  [{i+1}/{len(rows)}] {slug}: {question[:60]}...", end=" ", flush=True)

        t0 = time.time()
        try:
            response = _invoke_agent(slug, question)
            error = None
        except Exception as e:  # noqa: BLE001
            response, error = "", str(e)
        elapsed_ms = round((time.time() - t0) * 1000)

        if error:
            scores = {"pass": False, "negative_response": False, "all_criteria": False,
                      "criteria_covered": 0, "contains_expected": False,
                      "no_forbidden": True, "sufficient_length": False, "db_overlap": 0,
                      **{n: False for n in _CRITERIA}}
            reason = f"agent error: {error[:200]}"
        else:
            scores = _score_response(response, row, universe)
            reason = _build_reason(scores)

        verdict = "PASS" if scores["pass"] else "FAIL"
        print(f"{verdict} ({elapsed_ms}ms, {scores['criteria_covered']}/4 dims, "
              f"overlap {scores['db_overlap']})")

        results.append({
            "question": question,
            "expected_slug": slug,
            "agent_name": row["agent_name"],
            "category": row["category"],
            "pass": verdict,
            "geography": scores["geography"],
            "sub_sector": scores["sub_sector"],
            "ownership": scores["ownership"],
            "revenue_band": scores["revenue_band"],
            "criteria_covered": scores["criteria_covered"],
            "contains_expected": scores["contains_expected"],
            "no_forbidden": scores["no_forbidden"],
            "sufficient_length": scores["sufficient_length"],
            "negative_response": scores["negative_response"],
            "db_overlap": scores["db_overlap"],
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
    avg_ms = round(sum(r["elapsed_ms"] for r in results) / total) if total else 0
    avg_len = round(sum(r["response_length"] for r in results) / total) if total else 0
    avg_dims = round(sum(r["criteria_covered"] for r in results) / total, 2) if total else 0

    by_category: dict[str, dict] = {}
    for r in results:
        cat = r["category"]
        c = by_category.setdefault(cat, {"total": 0, "pass": 0, "fail": 0})
        c["total"] += 1
        c["pass" if r["pass"] == "PASS" else "fail"] += 1

    # Per-dimension coverage across all cases — where do the agents drop a criterion?
    dim_coverage = {
        n: sum(1 for r in results if r[n]) for n in _CRITERIA
    }

    return {
        "total": total,
        "pass": passed,
        "fail": total - passed,
        "pass_rate": round(passed / total * 100, 1) if total else 0,
        "avg_latency_ms": avg_ms,
        "avg_response_length": avg_len,
        "avg_dimensions_covered": avg_dims,
        "dimension_coverage": dim_coverage,
        "by_category": by_category,
        "failures": [
            {"slug": r["expected_slug"], "question": r["question"][:100], "reason": r["reason"]}
            for r in results if r["pass"] == "FAIL"
        ],
    }


def _print_universe(screen: dict):
    print("\nDeterministic DB screen (thesis run directly on pehero.companies):")
    print(f"  Verticals={list(SCREEN_VERTICALS)} (excl. veterinary + non-clinical) · "
          f"country∈{{EE,LT,LV}} · ownership∈{{founder,family}} · "
          f"revenue €{REVENUE_MIN_EUR:,}–€{REVENUE_MAX_EUR:,}")
    if not screen["ok"]:
        print(f"  {screen['note']}")
        return
    print(f"  Matches: {screen['count']}")
    for c in screen["companies"][:25]:
        rev = c.get("revenue_ltm")
        rev_s = f"€{float(rev)/1e6:.1f}M" if rev is not None else "n/a"
        print(f"    · {c['name']}  [{c.get('country')}] {c.get('sub_sector') or c.get('sector')} "
              f"· {c.get('ownership')} · {rev_s}")
    if screen["count"] == 0:
        print("  (No rows matched — seed Baltic health & dental data via "
              "scripts.scrape_ee + scripts.load_ee_data.)")


def main():
    parser = argparse.ArgumentParser(
        description="Screen eval: Baltic health, dental & dermatology clinics, "
                    "non-institutional ownership, €3-10M revenue")
    parser.add_argument("--slug", type=str, help="Test a single agent")
    parser.add_argument("--limit", type=int, default=100, help="Cap the DB universe size")
    parser.add_argument("--no-llm", action="store_true",
                        help="Run only the deterministic DB screen (no agent/LLM calls)")
    args = parser.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Layer 1 — always run the deterministic screen; it's the ground-truth universe.
    screen = screen_db(limit=args.limit)
    _print_universe(screen)

    universe_path = REPORTS_DIR / f"screen-universe-{ts}.csv"
    if screen["companies"]:
        with open(universe_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(screen["companies"][0].keys()))
            w.writeheader()
            w.writerows(screen["companies"])
        print(f"\n  Universe → {universe_path}")

    if args.no_llm:
        print("\n--no-llm: skipping agent behavioural eval.")
        return

    # Layer 2 — agent behavioural eval.
    rows = load_ground_truth(slug=args.slug)
    print(f"\nLoaded {len(rows)} screen eval cases · running agents (hits LLM) ...")
    results = evaluate(rows, screen["companies"])
    summary = summarize(results)

    csv_path = REPORTS_DIR / f"screen-eval-{ts}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)

    json_path = REPORTS_DIR / f"screen-eval-{ts}.json"
    json_path.write_text(json.dumps({**summary, "db_universe_size": screen["count"]}, indent=2))

    print(f"\nResults:")
    print(f"  Total:            {summary['total']}")
    print(f"  Pass:             {summary['pass']} ({summary['pass_rate']}%)")
    print(f"  Fail:             {summary['fail']}")
    print(f"  Avg latency:      {summary['avg_latency_ms']}ms")
    print(f"  Avg dims covered: {summary['avg_dimensions_covered']}/4")
    print(f"  Dimension coverage (cases addressing each): {summary['dimension_coverage']}")

    if summary["failures"]:
        print(f"\nFailures ({len(summary['failures'])}):")
        for f_ in summary["failures"]:
            print(f"  {f_['slug']}: {f_['reason']}")

    print(f"\nReports:")
    print(f"  {csv_path}")
    print(f"  {json_path}")

    try:
        from evals.generate_report import generate_xls_from_response
        xls_path = generate_xls_from_response(results, summary, ts)
        print(f"  {xls_path}")
    except Exception as e:  # noqa: BLE001 — XLS is a nice-to-have
        print(f"  (XLS export skipped: {str(e)[:120]})")


if __name__ == "__main__":
    main()
