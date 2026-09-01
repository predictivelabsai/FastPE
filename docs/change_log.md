# Changelog

## v0.8.1 — 2026-09-01

### Safe, consistently formatted agent responses
- Removed raw tool names, arguments, and result payloads from browser SSE events and live chat bubbles
- Converted web-search Markdown/HTML snippets into compact plain-text citation cards with safe source links
- Normalized assistant paragraph/list spacing in both the main chat and copilot
- Added a Market Scanner response contract for concise single-company fact lookups
- Added stream-privacy and tool-schema regression coverage; full suite: 156 passed, 2 skipped
- Pinned the existing Anthropic handbook-translation dependency so clean production installs pass dependency reachability checks
- Fixed the portfolio snapshot's zero-argument tool schema for current clean-install LangChain/Pydantic releases

## v0.7.0 — 2026-05-30

### Export suite + inline charts + table truncation
- Tables truncated to 5 preview rows with **See more / See less** toggle
- **Download XLS** button on every table — server-side .xlsx with styled headers (openpyxl)
- **Visualize** button on every table — auto-detects chart type (bar, area, pie, treemap, grouped bar), renders inline via Plotly.js (lazy-loaded)
- **Download Word** button on memo/LOI agents alongside PDF — server-side .docx with formatted headings, bold, tables, bullets (python-docx)
- New endpoints: `POST /app/export/xlsx`, `POST /app/export/docx`, `POST /app/chart`
- News pane opens by default, RSS pre-fetched on startup
- Refresh interval configurable via `config/params.yaml` (default 30 min)
- Added `openpyxl>=3.1.0`, `python-docx>=1.1.0` dependencies

## v0.6.0 — 2026-05-30

### News feed + inline artifacts
- Right pane reworked from canvas/artifact viewer to live **news feed** panel
- RSS feeds from FT, Bloomberg, WSJ, Reuters, BBC Business, ERR News, Baltic Times
- News article titles auto-translated via LLM when session language is non-English
- 5-minute server-side cache, auto-refresh every 5 minutes on the client
- Artifact tables and citations now render **inline in the chat bubble** instead of the right pane
- Memo PDF preview opens in a new browser tab instead of the right pane iframe
- Pipeline deal-detail page retains its deal-brief right pane (backwards compat)
- Added `feedparser>=6.0.0` dependency
- News i18n: title, loading, empty, time-ago keys in all 5 languages (EN/ET/LT/FI/SV)

## v0.5.0 — 2026-05-30

### Company Search page + Estonian scraper + batch scaling
- `/app/companies` — fuzzy name search (ILIKE) + sector filter, FastHTML table with revenue, EBITDA, employees, deal stage
- Added "Companies" to left-pane Workspace nav (between Pipeline and Instructions)
- Estonian company scraper (`scripts/scrape_ee.py`) — ssb.ee with EMTAK sector search, 30 EMTAK categories
- Lithuanian scraper extended to 1000 companies with pagination, 30 categories across 6 sectors
- `config/sources.yaml` — centralized source configuration for Lithuania + Estonia
- 30 regression test cases (tc01-tc30), all passing with real Lithuanian financial data
- Lithuanian product tour: 12 screenshots, PDF + PPTX slide decks

## v0.4.1 — 2026-05-29

### Purge synthetic data; add CSV regression suite
- All example prompts (24 agents) replaced with real Lithuanian companies: DR VET, Kardiolita, Northway, Baltic Transline, Eika Construction
- Removed all Northwind/Meridian/Acme references and USD examples from prompts, tools, tests, and UI
- `test-cases/regression.csv` — 20 test cases covering all agent categories with real company data
- `tests/regression_csv.py` — CSV-driven regression runner (dry-run for routing, full LLM for end-to-end)
- tc01 (Deal Triage) and tc02 (LTM Financials) verified end-to-end with real DB data

## v0.4.0 — 2026-05-29

### Real Lithuanian company data
- Replaced all synthetic data with 157 real Lithuanian companies scraped from rekvizitai.vz.lt
- 6 sub-sectors: health care (32), veterinary clinics (19), dental clinics (17), real estate (30), insurance (29), logistics (30)
- Multi-year financials: 7,524 monthly rows derived from public annual reports (2020-2025)
- Includes DR VET, Kardiolita/Meliva hospitals, Northway, Lietuvos Draudimas, Baltic Transline, and other notable companies
- `scripts/scrape_lt.py` — Playwright-based scraper with resume support and context crash recovery
- `scripts/load_lt_data.py` — transforms scraped JSON into PEHero schema, computes EBITDA proxy, growth rates, EV estimates
- `data/lt_companies.json` — raw scraped data (157 companies with addresses, employees, financials, descriptions)

## v0.3.1 — 2026-05-29

### Add Estonian, Finnish, Swedish
- Three new languages: Estonian (et), Finnish (fi), Swedish (sv) — all 256 UI keys + 24 agent names + 5 category names
- Estonian IP auto-detection for first-time visitors (Telia, Elisa, Tele2, Levikom, EENet ranges)
- Router language-intent regex expanded: Estonian, Finnish, Swedish language names now recognized
- Five flag selectors (🇬🇧 🇪🇪 🇱🇹 🇫🇮 🇸🇪) in chat header and landing navbar

## v0.3.0 — 2026-05-29

### Internationalisation (EN + LT)
- Full i18n infrastructure: `utils/i18n.py` with ~500 translation keys (English + Lithuanian)
- Landing pages fully translated: hero, nav, pricing, how-it-works, agents, contact
- Chat UI translated: left pane labels, header, input placeholders, sample cards, sign-in overlay, canvas
- Pipeline, analytics, and instructions pages translated
- Agent registry translations: 24 agent names + one-liners in Lithuanian
- Category translations: 5 PE workflow stages in Lithuanian
- Language flag selector (🇬🇧 / 🇱🇹) in chat header and landing navbar
- Session-based language persistence via cookie
- Lithuanian IP auto-detection for first-time visitors
- LLM language directive: agents automatically respond in Lithuanian when session language is set
- `static/chat.js` reads i18n JSON blob; 30+ hardcoded strings replaced with translated lookups

### Router language-intent fix
- Language-switching messages ("can you write in Lithuanian", "translate to English") no longer re-route to a different agent
- `is_language_intent()` pre-filter in `agents/router.py` detects language intents
- Chat stays on the current agent and the LLM handles the language switch via the session directive

### Versioning
- Added `utils/version.py` with semver + date
- Version displayed next to Beta badge in chat left pane

## v0.2.0 — 2026-05-29

### Prompt versioning + WYSIWYG editor
- `pehero.prompt_versions` table for audit trail
- Quill 2.0 WYSIWYG editor with markdown toggle and version history
- JSON API for version CRUD and revert
- Migration seeds existing prompts as v1

### Video tour
- `scripts/make_video.py` generates `docs/pehero.mp4` from screenshot frames

## v0.1.0 — 2026-05-28

- Initial release: 24 specialist PE agents, 3-pane chat, pipeline kanban, analytics (text-to-SQL), session sharing, memo PDF rendering, Baltic registry integrations
