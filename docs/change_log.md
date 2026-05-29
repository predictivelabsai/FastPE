# Changelog

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
