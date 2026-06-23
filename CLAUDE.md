# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PEHero — agentic AI for private equity. One FastHTML process hosting a marketing landing site, a 3-pane chat app, a pipeline kanban, an analytics (text-to-SQL → Plotly) page and in-app prompt editing. Backed by PostgreSQL (`pehero` OLTP schema + `pehero_rag` pgvector schema) and xAI Grok as the default LLM.

25 specialist agents are wired via LangGraph `create_react_agent`, routed by prefix / keywords / LLM fallback. 11 UI languages (EN, ET, LT, LV, FI, SV, NO, DA, FR, DE, PL) via `utils/i18n.py`. Public copy avoids naming the count — the product is pitched as "Your Private Equity AI Agent Squad".

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
pytest -q tests/test_agents_smoke.py             # 41 tests; build-every-agent, route, tool shape
pytest -q tests/test_agents_smoke.py::test_lbo_round_trip

# Full regression — HITS the LLM, writes docs/regression-latest.md
python -m tests.regression_suite                 # all 25 agents, their first example_prompt
python -m tests.regression_suite --slug deal_triage

# Daily deals email digest (Postmark) — sends to all opted-in users
python -m scripts.daily_deals                    # send to all verified users with notify_new_deals=TRUE
python -m scripts.daily_deals --to me@firm.com   # override: single recipient
python -m scripts.daily_deals --dry-run          # preview HTML, don't send
# Daemon thread in main.py sends at DIGEST_HOUR (default 7 EET). DIGEST_ENABLED=0 disables.

# Estonian ownership data (scrapes ariregister.rik.ee)
python -m scripts.scrape_ee_owners               # scrape + update DB
python -m scripts.scrape_ee_owners --dry-run     # preview, don't write
python -m scripts.scrape_ee_owners --limit 20    # first N companies

# Investor prospecting (persons from ee_owners.json + Äripäev wealth data)
python -m scripts.load_ee_persons                # load persons into DB
python -m scripts.load_ee_persons --dry-run      # preview counts
python -m scripts.load_ee_persons --fresh        # truncate + reload
python -m scripts.load_ee_persons --rich data/ee_rich.json  # merge wealth data
python -m scripts.scrape_ee_rich                 # scrape Äripäev richest list → data/ee_rich.json
python -m scripts.scrape_ee_rich --dry-run       # preview, don't write

# Regional data scrapers + loaders (LT, EE, LV, PL, RO)
python -m scripts.scrape_lt                      # scrape Lithuanian companies
python -m scripts.scrape_ee                      # scrape Estonian companies
python -m scripts.load_lt_data                   # load LT JSON into DB
python -m scripts.load_ee_data                   # load EE JSON into DB
# Also: scrape_lv, scrape_pl, scrape_ro, load_lv_data, load_pl_data, load_ro_data

# RAG document ingestion
python -m scripts.ingest_docs                    # index docs into pehero_rag

# Pipedrive CRM sync
python -m scripts.sync_pipedrive                 # sync companies → Pipedrive deals

# PE Handbook generation
python -m scripts.make_handbook                  # → docs/pe-handbook.md
python -m scripts.translate_handbook             # translate to ET/LT/RO

# User guide (A4 landscape PDF + 16:9 PPTX, requires pandoc + weasyprint)
bash scripts/build_user_guide.sh                 # → docs/pehero-user-guide.{pdf,pptx}

# Demo artifacts (requires a running server on :5058 and playwright chromium)
playwright install chromium                      # one-off
python -m scripts.capture_screenshots            # → ./screenshots/*.png (18 frames)
python -m scripts.make_gif                       # → docs/pehero.gif
python -m scripts.make_pdf                       # → docs/pehero-product-tour.pdf
python -m scripts.make_pptx                      # → docs/pehero-product-tour.pptx

# Evals (routing accuracy, response quality, game eval)
python -m evals.run_routing_eval                 # test agent routing accuracy
python -m evals.run_response_eval                # LLM response quality scoring
python -m evals.run_game_eval                    # PE Hero game eval

# Docker / Coolify deploy
docker compose up --build                        # local bring-up
# Coolify: DB_URL + XAI_API_KEY + GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET
#          + SERVICE_URL + POSTMARK_API_TOKEN; domain → pehero.chat, port 5058.
# docker-entrypoint.sh runs db.migrate on start. Synthetic seed stays manual:
#   docker compose exec web python -m synthetic.generate --seed 42
```

## Architecture

### Routes (one FastHTML `app.py` mounts everything)

- `/` + `/platform` + `/agents` + `/agents/<slug>` + `/how-it-works` + `/pricing` + `/contact` → `landing/`
- `/app` → 3-pane chat product. SSE streaming at `POST /app/chat`. `chat/routes.py`.
- `/app/pipeline` + `/app/pipeline/<slug>` → kanban board + per-deal workspace (chat + brief on right). `chat/pipeline.py`.
- `/app/companies` + `/app/companies/<slug>` → company/portfolio browser. `chat/companies.py`.
- `/app/investors` + `/app/investors/<slug>` → family office & investor prospecting (persons, wealth, company links). `chat/investors.py`.
- `/app/portfolio` → portfolio dashboard (KPIs, value bridge, health donut, top holdings). `/app/portfolio/analytics` → bubble chart, heatmap, sector allocation, holdings table. `/app/portfolio/kpis` → financial trend lines, margin targets, company scorecard. `chat/portfolio.py`.
- `/app/dataroom` + `/app/dataroom/<slug>` → virtual data room file tree + RAG indexing. `chat/dataroom.py`.
- `/app/instructions` + `/app/instructions/<slug>` → live-edit each agent's prompt. Writes to `prompts/system/<slug>.md`, clears the agent cache. `chat/instructions.py`.
- `/app/analytics` + `POST /app/analytics/run` → text → SELECT SQL (guarded) → Plotly figure. `chat/analytics.py`.
- `/app/valuation` → PE valuation simulator (DCF, comps, precedent, LBO). `chat/valuation.py`.
- `/app/integrations` → Pipedrive CRM sync + data source status. `chat/integrations.py`.
- `/app/help` → user guide. `chat/help.py`.
- `/app/training` → PE Hero RPG game. SSE streaming at `POST /app/training/chat`. `chat/training.py` → `game/routes.py`.
- `/app/profile` → user preferences (deal criteria, notifications). `auth/routes.py`.
- `/app/s/{token}` → public read-only shared chat view. `POST /app/share` generates the token. `chat/routes.py`.
- `/app/memo-pdf/render` + `/app/export/docx` + `/app/export/xlsx` → document export. `chat/memo_pdf.py` + `chat/exports.py`.
- `POST /app/config` → session currency + language preference.
- `/auth/*` → registration, login, email verification, password reset, Google OAuth. `auth/routes.py`.
- `/app/webhooks/*` → Pipedrive webhooks. `chat/webhooks.py`.
- `/app/_debug/ping` → LLM health check.

### Agents (`agents/`)

- `registry.py` holds all 25 `AgentSpec`s (slug, name, category, icon, prefix, one-liner, description, 4+ example_prompts). Categories: `sourcing (7) | underwriting (5) | diligence (5) | capital (4) | asset_mgmt (4)`. The display label for `asset_mgmt` is "Portfolio Operations".
- `router.py` resolves a user message to a slug in three steps: explicit prefix → keyword score → LLM classifier. Falls back to `deal_triage`.
- `base.py::cached_agent(slug)` imports `agents.<category>.<slug>` and calls `build()`. Every agent module exports `SPEC`, `TOOLS`, `build()`. `build()` reads `prompts/shared/pe_context.md` + `prompts/system/<slug>.md` and wraps tools in a LangGraph ReAct agent.
- The chat route (`chat/routes.py`) prepends a `SystemMessage` with the session's currency preference on every run, so every specialist defaults to the user's currency without a prompt rewrite.

### Tools (`tools/`)

- Filenames are legacy Bricksmith-CRE but contents are PE-native. `tools/rentroll.py` queries `pehero.cap_tables`; `tools/properties.py` queries `pehero.companies`; etc. Each module exports both a PE-native name (`search_companies`, `summarize_cap_table`, `normalize_ltm`, `build_lbo_model`, `size_debt_stack`, `abstract_contracts`, `audit_vdr`, …) and legacy aliases (`search_properties`, `summarize_rent_roll`, `normalize_t12`, `build_pro_forma`, `size_debt`, `abstract_leases`, `audit_doc_room`) for back-compat within agent modules.
- `tools/search.py` — Tavily (default) → EXA (fallback) web search. Wired into the 4 sourcing agents.
- `tools/baltic.py` + `tools/registry/{ee,lt,lv}.py` — uniform `baltic_lookup / baltic_filings / baltic_tax_status` surface. Returns `stub=True` until the country API keys are set. Full setup in `docs/registry_integration.md`.
- `tools/rag.py` → semantic search over `pehero_rag.documents` via `rag/retriever.py`.
- `utils/scoring.py` — PE triage scoring (40% impact, 30% strategic fit, 20% feasibility, 10% urgency → 1.0–5.0 weighted total, High/Medium/Low band). Used by synthetic data + pipeline cards.
- Tools that produce UI artifacts return a string prefixed `__ARTIFACT__{json}` — the SSE layer picks it up, forwards it as an `artifact_show` event, and `static/chat.js` renders it in the right pane.

### Data model (`db/schema.sql`)

Core tables all live in `pehero.*`:
`companies, funds, cap_tables, financials (monthly), contracts, transaction_comps, trading_comps, lbo_models, debt_stacks, investor_crm, market_signals, dd_findings, deal_risks, deal_milestones, portfolio_kpis, users, user_preferences, chat_sessions, chat_messages, agent_invocations, prompt_versions, data_room, pipedrive_sync, outreach_sequences, user_integrations, digest_sends, persons, person_company_links`.

`pehero_rag.*` holds `documents, chunks, embeddings (vector({{EMBEDDING_DIM}}))`. `EMBEDDING_DIM` is substituted at migrate time — changing it requires `db.migrate --drop` and re-indexing.

### Front-end (`chat/components.py` + `static/`)

- Left pane: New-chat + session list, agent browser (5 categories × 25 agents), Workspace (Pipeline / Companies / Investors / Data Room / Instructions / Analytics / Valuation / Portfolio / Integrations), Training (User Guide + PE Hero Game), Configuration (currency + language switcher). All routes pass `current_currency=get_currency(sess)` and `lang=get_lang(sess)` to `left_pane()`.
- `static/app.css` holds base chat + left-pane + thinking indicator + follow-up + sample-cards + currency-chip rules. `static/pipeline.css` holds kanban + deal-detail + instructions + analytics rules (pipeline.css is only loaded on those routes; anything that also appears on `/app` must live in `app.css`).
- `static/chat.js` handles SSE streaming, thinking-indicator (timer + rotating tool name), contextual sample cards (per agent — prompt tables embedded as `<script id="agent-prompts-data">`), the "Next step — Yes / No" follow-up pattern, Copy chat / Share link (clipboard + `POST /app/share`), memo → PDF/Word export, table → CSV/XLS export + Plotly visualize, and the currency/language selectors.

### Auth (`auth/`)

- `routes.py` — register (bcrypt), login, email verify (token), forgot/reset password (1-hr token), Google OAuth 2.0 (code → userinfo → upsert), user profile + deal preferences, token-based unsubscribe. All DB via `db.connect()` + `fetch_one()`.
- `utils.py` — `hash_password()`, `verify_password()`, `generate_token()`, Postmark email senders (`send_verification_email`, `send_reset_email`).
- `utils/email.py` — generic Postmark `send_email()` wrapper (httpx, not requests).
- Auth columns on `pehero.users`: `password_hash`, `name`, `is_verified`, `verify_token`, `reset_token`, `reset_token_expires`. User preferences in `pehero.user_preferences` (deal size, revenue/EBITDA ranges, JSONB sectors/deal_types/geographies, notification booleans, unsubscribe_token). Both managed via `ALTER TABLE … ADD COLUMN IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS` in `db/migrate.py`.

### Game (`game/`)

- PE Hero — an RPG training game at `/app/training`. Players pick a character, navigate PE deal scenarios with real companies from the DB, make decisions, and earn scores.
- `engine.py` — game state, levels, characters, deal pipeline, scoring.
- `agent.py` — LangGraph ReAct agent with 8 game tools (close deals, advance stages, adjust resources, etc.).
- `prompts.py` — game master system prompt, welcome/game-over templates.
- `routes.py` — SSE streaming chat + reset endpoint. Registered via `register_game_routes(rt)` in `app.py`.

### Session state

Cookies via Starlette's `SessionMiddleware`. Helpers in `utils/session.py`: `get_user_email`, `get_user_id`, `get_currency` (EUR default), `set_currency`, `currency_symbol`. Constants `CURRENCIES = ("EUR", "GBP", "USD")`, `SYMBOLS = {"EUR": "€", "GBP": "£", "USD": "$"}`. Language helpers in `utils/i18n.py`: `get_lang`, `set_lang`, `t()` (UI string lookup), `agent_t()` (agent name/description lookup). IP-based language auto-detection for Baltic visitors.

## Conventions

- **All LLM calls** go through `utils.llm.build_llm()` / `build_agent_llm()` — never construct `ChatOpenAI` elsewhere.
- Schemas `pehero.*` and `pehero_rag.*` are always qualified in SQL — never rely on `search_path`.
- Synthetic data is deterministic given `--seed`. Keep it that way so the smoke tests stay stable.
- User-facing copy does **not** mention "25 agents" or "$0 / synthetic data". Use "squad" language and "BYOD — bring your own data". Internal docstrings and this file can still mention the count.
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
INTERNAL = {'agents','app','auth','chat','config','db','evals','game','landing','prompts','rag','scripts','sql','static','synthetic','tests','tools','utils'}
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
.venv/bin/python -c "from app import app; from chat import routes, pipeline, instructions, analytics, companies, memo_pdf, exports, dataroom, help, valuation, webhooks, integrations, training, investors, portfolio; from auth import routes as _auth; print('app imports OK')"
```

Only push once all three pass. If you added a new dependency, pin it with a lower bound (`pkg>=X.Y.0`) in `requirements.txt` in the same commit that introduces the import.
