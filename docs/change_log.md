# Changelog

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
