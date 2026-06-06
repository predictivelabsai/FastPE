# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PEHero — agentic AI for private equity. One FastHTML process hosting a marketing landing site, a 3-pane chat app, a pipeline kanban, an analytics (text-to-SQL → Plotly) page and in-app prompt editing. Backed by PostgreSQL (`pehero` OLTP schema + `pehero_rag` pgvector schema) and xAI Grok as the default LLM.

24 specialist agents are wired via LangGraph `create_react_agent`, routed by prefix / keywords / LLM fallback. Public copy avoids naming the count — the product is pitched as "Your Private Equity AI Agent Squad".

## Commands

All commands assume `source .venv/bin/activate` (or use `.venv/bin/python` directly).

```bash
# Setup
cp .env.example .env                             # fill DB_URL + XAI_API_KEY
pip install -r requirements.txt
python -m db.migrate                             # idempotent; creates pehero + pehero_rag + pgvector
python -m db.migrate --drop                      # DESTRUCTIVE — drops both schemas

# Seed synthetic data (deterministic for a given seed)
python -m synthetic.generate --seed 42           # full seed
python -m synthetic.generate --seed 42 --fresh   # truncate then re-seed (keeps chat history)
python -m synthetic.generate --skip-rag          # OLTP only
python -m synthetic.generate --limit 5           # small subset for fast iteration

# Run
PORT=5058 python main.py                         # :5058 is the default

# Smoke tests (no LLM)
pytest -q tests/test_agents_smoke.py             # 38 tests; build-every-agent, route, tool shape
pytest -q tests/test_agents_smoke.py::test_lbo_round_trip

# Full regression — HITS the LLM, writes docs/regression-latest.md
python -m tests.regression_suite                 # all 24 agents, their first example_prompt
python -m tests.regression_suite --slug deal_triage

# Daily deals email digest (Postmark)
python -m scripts.daily_deals                    # send to DAILY_DEALS_TO_EMAIL
python -m scripts.daily_deals --to me@firm.com   # override recipient
python -m scripts.daily_deals --dry-run          # preview HTML, don't send
# Cron (8:00 AM EET daily):
#   0 8 * * * cd /path/to/pehero && .venv/bin/python -m scripts.daily_deals

# Demo artifacts (requires a running server on :5058 and playwright chromium)
playwright install chromium                      # one-off
python -m scripts.capture_screenshots            # → ./screenshots/*.png (18 frames)
python -m scripts.make_gif                       # → docs/pehero.gif
python -m scripts.make_pdf                       # → docs/pehero-product-tour.pdf
python -m scripts.make_pptx                      # → docs/pehero-product-tour.pptx

# Docker / Coolify deploy
docker compose up --build                        # local bring-up
# Coolify: just DB_URL + XAI_API_KEY; domain → pehero.fyi, port 5058.
# docker-entrypoint.sh runs db.migrate on start. Synthetic seed stays manual:
#   docker compose exec web python -m synthetic.generate --seed 42
```

## Architecture

### Routes (one FastHTML `app.py` mounts everything)

- `/` + `/platform` + `/agents` + `/agents/<slug>` + `/how-it-works` + `/pricing` + `/contact` → `landing/`
- `/app` → 3-pane chat product. SSE streaming at `POST /app/chat`.
- `/app/pipeline` + `/app/pipeline/<slug>` → kanban board + per-deal workspace (chat + brief on right). `chat/pipeline.py`.
- `/app/instructions` + `/app/instructions/<slug>` → live-edit each agent's prompt. Writes to `prompts/system/<slug>.md`, clears the agent cache. `chat/instructions.py`.
- `/app/analytics` + `POST /app/analytics/run` → text → SELECT SQL (guarded) → Plotly figure. `chat/analytics.py`.
- `POST /app/config` → session currency preference (EUR default; GBP / USD available).
- `/app/_debug/ping` → LLM health check.

### Agents (`agents/`)

- `registry.py` holds all 22 `AgentSpec`s (slug, name, category, icon, prefix, one-liner, description, 4+ example_prompts). Categories: `sourcing | underwriting | diligence | capital | asset_mgmt`. The display label for `asset_mgmt` is "Portfolio Operations".
- `router.py` resolves a user message to a slug in three steps: explicit prefix → keyword score → LLM classifier. Falls back to `deal_triage`.
- `base.py::cached_agent(slug)` imports `agents.<category>.<slug>` and calls `build()`. Every agent module exports `SPEC`, `TOOLS`, `build()`. `build()` reads `prompts/shared/pe_context.md` + `prompts/system/<slug>.md` and wraps tools in a LangGraph ReAct agent.
- The chat route (`chat/routes.py`) prepends a `SystemMessage` with the session's currency preference on every run, so every specialist defaults to the user's currency without a prompt rewrite.

### Tools (`tools/`)

- Filenames are legacy Bricksmith-CRE but contents are PE-native. `tools/rentroll.py` queries `pehero.cap_tables`; `tools/properties.py` queries `pehero.companies`; etc. Each module exports both a PE-native name (`search_companies`, `summarize_cap_table`, `normalize_ltm`, `build_lbo_model`, `size_debt_stack`, `abstract_contracts`, `audit_vdr`, …) and legacy aliases (`search_properties`, `summarize_rent_roll`, `normalize_t12`, `build_pro_forma`, `size_debt`, `abstract_leases`, `audit_doc_room`) for back-compat within agent modules.
- `tools/search.py` — Tavily (default) → EXA (fallback) web search. Wired into the 4 sourcing agents.
- `tools/baltic.py` + `tools/registry/{ee,lt,lv}.py` — uniform `baltic_lookup / baltic_filings / baltic_tax_status` surface. Returns `stub=True` until the country API keys are set. Full setup in `docs/registry_integration.md`.
- `tools/rag.py` → semantic search over `pehero_rag.documents` via `rag/retriever.py`.
- Tools that produce UI artifacts return a string prefixed `__ARTIFACT__{json}` — the SSE layer picks it up, forwards it as an `artifact_show` event, and `static/chat.js` renders it in the right pane.

### Data model (`db/schema.sql`)

Core tables all live in `pehero.*`:
`companies, funds, cap_tables, financials (monthly), contracts, transaction_comps, trading_comps, lbo_models, debt_stacks, investor_crm, market_signals, dd_findings, portfolio_kpis, users, chat_sessions, chat_messages, agent_invocations`.

`pehero_rag.*` holds `documents, chunks, embeddings (vector({{EMBEDDING_DIM}}))`. `EMBEDDING_DIM` is substituted at migrate time — changing it requires `db.migrate --drop` and re-indexing.

### Front-end (`chat/components.py` + `static/`)

- Left pane: New-chat + session list, agent browser (5 categories × 24 agents), Workspace (Pipeline / Instructions / Analytics), Configuration (currency switcher). All routes pass `current_currency=get_currency(sess)` to `left_pane()`.
- `static/app.css` holds base chat + left-pane + thinking indicator + follow-up + sample-cards + currency-chip rules. `static/pipeline.css` holds kanban + deal-detail + instructions + analytics rules (pipeline.css is only loaded on those routes; anything that also appears on `/app` must live in `app.css`).
- `static/chat.js` handles SSE streaming, thinking-indicator (timer + rotating tool name), contextual sample cards (per agent — prompt tables embedded as `<script id="agent-prompts-data">`), the "Next step — Yes / No" follow-up pattern, and the currency selector (`POST /app/config`, reload).

### Session state

Cookies via Starlette's `SessionMiddleware`. Helpers in `utils/session.py`: `get_user_email`, `get_user_id`, `get_currency` (EUR default), `set_currency`, `currency_symbol`. Constants `CURRENCIES = ("EUR", "GBP", "USD")`, `SYMBOLS = {"EUR": "€", "GBP": "£", "USD": "$"}`.

## Conventions

- **All LLM calls** go through `utils.llm.build_llm()` / `build_agent_llm()` — never construct `ChatOpenAI` elsewhere.
- Schemas `pehero.*` and `pehero_rag.*` are always qualified in SQL — never rely on `search_path`.
- Synthetic data is deterministic given `--seed`. Keep it that way so the smoke tests stay stable.
- User-facing copy does **not** mention "24 agents" or "$0 / synthetic data". Use "squad" language and "BYOD — bring your own data". Internal docstrings and this file can still mention the count.
- Public marketing renders monetary figures in **EUR** (`€`). In-app figures follow the session's currency preference via `currency_symbol(get_currency(sess))`.
- Agent module filenames (`rent_roll_parser.py`, `leases.py`, `t12_normalizer.py`, etc.) and tool filenames still mirror the Bricksmith origin. Public names in `AgentSpec` and all prompts/synthetic content are PE-specific. Don't be surprised by the mismatch.
- When you rename or add an agent slug, remember: module path (`agents/<category>/<slug>.py`) must match, `prompts/system/<slug>.md` must exist, and the router's `_best_in_category_for` + `CATEGORY_HINTS` keyword maps might need updating too.
- When you add a UI rule used on `/app`, put the CSS in `static/app.css`, not `static/pipeline.css` — the latter isn't loaded on the base chat route.
- Favicon lives in `static/favicon.{svg,png,ico}` + `apple-touch-icon.png`. `landing.components._favicon_links()` renders the `<link>`s; `chat/layout.py` and the three sub-page `_head()` helpers (`pipeline.py`, `instructions.py`, `analytics.py`) all import and splat it.
- **Minimize JavaScript — leverage FastHTML.** Render HTML server-side with FastHTML components wherever possible. Use JS only for interactions that require it (SSE streaming, clipboard, dynamic pane toggling). Tables, headings, lists, and other structural content in persisted messages must be rendered server-side in `_render_content()`. For live-streaming responses, `marked.js` handles markdown → HTML; after streaming completes the server-side renderer takes over on next page load.

## Pre-commit / pre-push checks

**Always run this block before `git commit` / `git push` — production has already gone down once because a dev-only install was missed:**

```bash
# 1. Every new third-party import must be reachable from requirements.txt.
#    Whenever a commit adds a non-stdlib, non-internal import, confirm the
#    top-level package is either pinned directly or a transitive dep of a
#    pinned package. The Coolify image runs a clean
#    `pip install -r requirements.txt`; anything installed locally via
#    `uv pip install` but not pinned will crash the container at startup
#    (and the site will just 404 because app.py imports chat modules
#    eagerly).
.venv/bin/python -c "
import ast, pathlib, re, sys
from importlib.metadata import packages_distributions, requires
ROOT = pathlib.Path('.')

# Direct deps from requirements.txt (distribution names, lower-case).
req = (ROOT / 'requirements.txt').read_text()
direct = set()
for line in req.splitlines():
    line = line.strip()
    if not line or line.startswith('#'): continue
    name = re.split(r'[\\[<>=~!]', line, 1)[0].strip().lower()
    if name: direct.add(name)

def norm(s): return re.sub(r'[-_.]+', '-', s).lower()

# Walk the dep graph to build the set of distributions actually reachable
# from a fresh pip install -r requirements.txt.
reachable = set()
def expand(pkg):
    n = norm(pkg)
    if n in reachable: return
    reachable.add(n)
    try:
        for r in (requires(pkg) or []):
            dep = re.split(r'[\\[<>=~!; ]', r, 1)[0].strip()
            if dep: expand(dep)
    except Exception: pass
for p in direct: expand(p)

# Map top-level import name → distribution name(s) on this machine.
dists = {k: [norm(d) for d in v] for k, v in packages_distributions().items()}
INTERNAL = {'agents','app','chat','db','landing','prompts','rag','scripts','static','synthetic','tests','tools','utils'}
stdlib = set(sys.stdlib_module_names)
missing = set()
for p in ROOT.rglob('*.py'):
    if any(x in str(p) for x in ('.venv','__pycache__','.git','screenshots')): continue
    tree = ast.parse(p.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [n.name.split('.')[0] for n in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module.split('.')[0]]
        else: continue
        for top in names:
            if top in stdlib or top in INTERNAL: continue
            candidates = set(dists.get(top, [norm(top)]))
            if not candidates & reachable:
                missing.add(f'{top}  ({p})')
print('OK' if not missing else 'MISSING FROM requirements.txt:\\n' + '\\n'.join(sorted(missing)))
"

# 2. Smoke tests still green.
pytest -q tests/test_agents_smoke.py

# 3. Offline boot check — every route module that app.py imports at
#    startup must import cleanly with only what's installed.
.venv/bin/python -c "from app import app; from chat import routes, pipeline, instructions, analytics, memo_pdf; print('app imports OK')"
```

Only push once all three pass. If you added a new dependency, pin it with a lower bound (`pkg>=X.Y.0`) in `requirements.txt` in the same commit that introduces the import.
