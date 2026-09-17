"""End-to-end regression across all registered agents.

Hits the real LLM (XAI_API_KEY required). Each agent is invoked with its
first example_prompt; we capture the final answer + any tool calls it made
and write a markdown report so failures are easy to review.

Not part of the fast pytest suite — run explicitly:

    python -m tests.regression_suite            # all agents, report to docs/regression-latest.md
    python -m tests.regression_suite --slug deal_triage   # one agent
    python -m tests.regression_suite --timeout 60         # per-agent timeout (s)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from agents.base import cached_agent
from agents.registry import AGENTS, AGENTS_BY_SLUG

log = logging.getLogger(__name__)

REPORT_PATH = Path(__file__).resolve().parent.parent / "docs" / "regression-latest.md"


def _extract_final(result) -> tuple[str, list[str]]:
    """Pull the final assistant text + names of tools called from a LangGraph result."""
    messages = result.get("messages") if isinstance(result, dict) else None
    if not messages:
        return (str(result)[:500], [])

    tools_called: list[str] = []
    final_text = ""
    for m in messages:
        # LangChain message objects expose .type and .content; handle dicts too
        m_type = getattr(m, "type", None) or (m.get("type") if isinstance(m, dict) else None)
        content = getattr(m, "content", None) or (m.get("content") if isinstance(m, dict) else None)
        tool_calls = getattr(m, "tool_calls", None) or (m.get("tool_calls") if isinstance(m, dict) else None)
        if tool_calls:
            for tc in tool_calls:
                name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                if name:
                    tools_called.append(name)
        if m_type in ("ai", "assistant") and content:
            final_text = content if isinstance(content, str) else str(content)
    return (final_text, tools_called)


def _run_agent(slug: str, prompt: str, timeout: float) -> dict:
    t0 = time.time()
    try:
        graph = cached_agent(slug)
        # LangGraph react agents take {"messages": [(role, content)]}
        result = graph.invoke(
            {"messages": [("user", prompt)]},
            config={"recursion_limit": 20},
        )
        final, tools = _extract_final(result)
        elapsed = time.time() - t0
        return {
            "slug": slug, "prompt": prompt, "status": "ok",
            "elapsed_s": round(elapsed, 2),
            "tools_used": tools,
            "final": (final or "").strip()[:1800],
            "error": None,
        }
    except Exception as e:  # noqa: BLE001
        elapsed = time.time() - t0
        return {
            "slug": slug, "prompt": prompt, "status": "error",
            "elapsed_s": round(elapsed, 2),
            "tools_used": [],
            "final": "",
            "error": f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1200:]}",
        }


def _render_report(results: list[dict], started: datetime) -> str:
    ok = sum(1 for r in results if r["status"] == "ok")
    total = len(results)
    avg = round(sum(r["elapsed_s"] for r in results) / max(1, total), 1)
    lines = [
        f"# PEHero agent regression — {started.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"**{ok}/{total} passed** · avg {avg}s per agent",
        "",
        "| Slug | Status | Time | Tools used | Preview |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        preview = (r["final"] or r.get("error") or "").replace("|", "\\|").replace("\n", " ")[:80]
        tools = ", ".join(r["tools_used"][:4]) or "—"
        lines.append(
            f"| `{r['slug']}` | {'✅' if r['status'] == 'ok' else '❌'} "
            f"| {r['elapsed_s']}s | {tools} | {preview} |"
        )
    lines.append("")
    lines.append("## Details")
    for r in results:
        lines.append(f"\n### `{r['slug']}` — {r['status'].upper()} ({r['elapsed_s']}s)")
        lines.append(f"**Prompt:** {r['prompt']}")
        if r["tools_used"]:
            lines.append(f"**Tools:** {', '.join(r['tools_used'])}")
        if r["status"] == "ok":
            lines.append("\n```")
            lines.append(r["final"] or "(empty)")
            lines.append("```")
        else:
            lines.append("\n```\n" + (r["error"] or "") + "\n```")
    return "\n".join(lines)


def run(slugs: list[str] | None = None, timeout: float = 90.0) -> int:
    started = datetime.utcnow()
    targets = [AGENTS_BY_SLUG[s] for s in slugs] if slugs else list(AGENTS)
    print(f"Running {len(targets)} agents — report → {REPORT_PATH}")
    results = []
    for i, spec in enumerate(targets, 1):
        prompt = spec.example_prompts[0] if spec.example_prompts else f"Hello, {spec.name}"
        print(f"  [{i}/{len(targets)}] {spec.slug}: {prompt[:60]}")
        r = _run_agent(spec.slug, prompt, timeout)
        status = "✓" if r["status"] == "ok" else "✗"
        print(f"     {status} {r['elapsed_s']}s — {len(r['final'])} chars · tools: {','.join(r['tools_used'][:3]) or '—'}")
        results.append(r)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(_render_report(results, started))
    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\nDone: {ok}/{len(results)} passed. Report: {REPORT_PATH}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", action="append", help="Run only this slug (repeatable).")
    ap.add_argument("--timeout", type=float, default=90.0)
    args = ap.parse_args()
    sys.exit(run(slugs=args.slug, timeout=args.timeout))
