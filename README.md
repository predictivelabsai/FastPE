# PEHero

Agentic AI for private equity — specialist agents that source, underwrite, close, and operate your deals.

![PEHero product tour](docs/pehero.gif)

Product tour — [PDF](docs/pehero-product-tour.pdf) · [PPTX](docs/pehero-product-tour.pptx) · User guide — [PDF](docs/pehero-user-guide.pdf) · [PPTX](docs/pehero-user-guide.pptx)

- **Marketing landing** at `/` with hero, agent directory, how-it-works, pricing, PE news feed.
- **3-pane chat app** at `/app` — left agent/session browser, centre chat with inline tables/charts, right PE news pane.
- **LangGraph ReAct agents** across deal sourcing, LBO underwriting, due diligence, capital/LP, and portfolio operations — routed by prefix (`triage:`, `lbo:`, `memo:`...) or by keyword heuristics with an LLM fallback classifier.
- **Pipeline kanban** — deal stages from Sourced to Exited with per-deal workspaces, triage scoring (40/30/20/10 weighted priority), risk register (P×I), and milestone tracking.
- **Portfolio management** — 3-tab submenu (Dashboard, Analytics, KPIs) with value bridge, health donut, bubble charts, heatmaps, and financial trend lines.
- **Investors** — family office & investor prospecting with 2,500+ persons, wealth data, and company links across Estonia, Lithuania, and Latvia.
- **PE Valuation Simulator** — 4-method valuation (EV/Revenue, EV/EBITDA, EV/EBIT, DCF) with WACC calculator, Damodaran industry multiples (96 industries), equity bridge, Plotly charts, and XLS export.
- **Data Room** with virtual folder tree, file upload, and automatic RAG indexing (PDF, DOCX, XLSX, PPTX).
- **Analytics** — natural language to SQL with auto-charting (Plotly).
- **Training** — PE Hero RPG game for practicing deal-making with real companies.
- **Copilot** — contextual AI assistant on every workspace page. Auto-injects page context and routes to the best specialist agent.
- **11 languages** — EN, ET, LT, LV, FI, SV, NO, DA, FR, DE, PL.
- **xAI Grok** as the default LLM via OpenAI-compatible endpoint.
- **PostgreSQL** with two schemas: `pehero` (OLTP — 1,800+ companies from Baltic registries, financials, contracts, comps, LBO models, debt stacks, LP CRM, deal risks, milestones) and `pehero_rag` (pgvector — document RAG with semantic search).
- **Local embeddings** via fastembed (no API key required) — BAAI/bge-small-en-v1.5 at 384 dim.

## Running locally

```bash
cp .env.example .env                    # fill DB_URL + XAI_API_KEY
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m db.migrate                    # creates pehero + pehero_rag schemas
python -m synthetic.generate --seed 42  # populate OLTP + RAG (~1 min)
python main.py                          # serves on :5058
```

Smoke test: `curl http://localhost:5058/app/_debug/ping` → `{"ok": true, "reply": "pong"}`.
End-to-end test: `pytest -q tests/`.

## Running in Docker (local)

```bash
DB_URL=... XAI_API_KEY=... docker compose up --build
```

On boot, the container runs `python -m db.migrate` automatically (idempotent).
Seed synthetic data once with:

```bash
docker compose exec web python -m synthetic.generate --seed 42
```

## Deploying to Coolify (pehero.fyi)

1. Point Coolify at this repo (Docker Compose build type).
2. Set environment variables in Coolify:
   - `DB_URL` — managed Postgres with pgvector enabled
   - `XAI_API_KEY`
3. Attach the `pehero.fyi` domain (port 5058).
4. First deploy only: `docker compose exec web python -m synthetic.generate --seed 42` from Coolify's terminal to populate synthetic data. Subsequent deploys re-run `db.migrate` automatically and leave your data in place.

## Claude Code slash commands

This project includes slash commands for [Claude Code](https://claude.ai/code) (`.claude/commands/`):

| Command | Description |
|---------|-------------|
| `/build-user-guide` | Rebuild user guide as A4 landscape PDF + 16:9 PPTX (pandoc → WeasyPrint + python-pptx) |
| `/build-product-tour` | Generate product tour slide deck as PDF + PPTX (ReportLab + python-pptx) |
| `/build-handbook` | Generate PE handbook PDF + EPUB with Plotly charts and Baltic case studies |
| `/capture-screenshots` | Run Playwright to capture product screenshots for docs |
| `/seed-data` | Generate deterministic synthetic data (companies, financials, risks, milestones, comps, LPs) |
| `/run-tests` | Smoke tests (41, no LLM), full regression (25 agents), routing/response/game evals |
| `/scrape-data` | Scrape Baltic company registries (EE, LT, LV, PL, RO) and load into DB |
| `/deploy` | Docker / Coolify deployment checklist and environment variables |

## Directory layout

```
main.py              entrypoint (thin shim)
app.py               FastHTML app, mounts landing + chat
landing/             / /platform /agents /agents/<slug> /how-it-works /pricing /contact
chat/                /app + /app/chat (SSE stream) + /app/auth/*
agents/              registry + router + 5 category packages (25 agents)
tools/               StructuredTools: companies, captable, financials, market, diligence, capital, asset, rag
db/                  schema.sql, rag_schema.sql, migrate.py
rag/                 embeddings (pluggable), indexer, retriever
synthetic/           PE dataset + DD doc generators + RAG ingest
prompts/             per-agent system prompts + shared PE glossary
scripts/             scrapers, loaders, doc builders, email digest
docs/                user guide, PE handbook, product tour (md + pdf + pptx)
.claude/commands/    Claude Code slash commands
```
