# Pipedrive Integration — Deal Sourcing & LP Fundraising

## Overview

Bidirectional sync between PEHero and Pipedrive CRM. PEHero's AI agents draft outreach, score leads, and move deals through stages; Pipedrive serves as the team-facing CRM UI. Changes in either system propagate to the other via webhooks + API polling fallback.

Two Pipedrive pipelines:
1. **Deal Sourcing** — company screening → LOI → closing
2. **LP Fundraising** — prospect → commitment → funded

## Architecture

```
┌─────────────┐   webhooks    ┌──────────────┐
│  Pipedrive  │──────────────▶│   PEHero     │
│  (CRM UI)   │◀──────────────│  (AI agents) │
└─────────────┘   API calls   └──────────────┘
       │                             │
       │  team edits deals,          │  agents draft emails,
       │  logs calls, moves          │  score leads, run
       │  stages, adds notes         │  comps, build LBO
       │                             │  models, move stages
       ▼                             ▼
   ┌──────────────────────────────────┐
   │  PostgreSQL (pehero.*)           │
   │  companies, investor_crm,       │
   │  pipedrive_sync (new table)     │
   └──────────────────────────────────┘
```

## Authentication — Current

Per-user personal API tokens, resolved in this order:

1. **Per-user token** from `pehero.user_integrations` (user pastes in Integrations UI)
2. **Global fallback** from `PIPEDRIVE_API_TOKEN` in `.env` (admin/demo)
3. **Stub mode** — no token → all functions return fake data

All API calls use **v1** with `api_token` query parameter auth.
Base URL: `https://{domain}.pipedrive.com/api/v1/`.

### DB table: `pehero.user_integrations`

```sql
CREATE TABLE pehero.user_integrations (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES pehero.users(id) ON DELETE CASCADE,
    provider    TEXT NOT NULL,         -- pipedrive | hubspot | ...
    api_token   TEXT NOT NULL,
    domain      TEXT,                  -- e.g. "predictivelabsltd"
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, provider)
);
```

### Connect flow

1. User navigates to `/app/integrations`
2. Pastes personal API token + company domain
3. `POST /app/integrations/connect` validates via `GET /api/v1/users/me`
4. On success, saves to `user_integrations` and redirects back
5. Disconnect removes the row

## Authentication — Multi-Tenant OAuth (future upgrade)

When PEHero ships as a multi-tenant SaaS, personal API tokens become impractical
(users shouldn't need to find their Pipedrive settings page). The upgrade path:

### 1. Register a Pipedrive App

Go to `https://developers.pipedrive.com` → create a private app (no marketplace
review needed for internal use; publish for public distribution).

This gives you:
- `PIPEDRIVE_CLIENT_ID`
- `PIPEDRIVE_CLIENT_SECRET`
- Redirect URI: `https://pehero.fyi/app/integrations/pipedrive/callback`

### 2. OAuth Flow

```
User clicks "Connect Pipedrive"
  → redirect to https://oauth.pipedrive.com/oauth/authorize
      ?client_id={CLIENT_ID}
      &redirect_uri={CALLBACK_URL}
      &state={csrf_token}

User authorizes on Pipedrive
  → redirect back to /app/integrations/pipedrive/callback?code={code}&state={state}

Server exchanges code for tokens:
  POST https://oauth.pipedrive.com/oauth/token
    grant_type=authorization_code
    &code={code}
    &redirect_uri={CALLBACK_URL}
    &client_id={CLIENT_ID}
    &client_secret={CLIENT_SECRET}

Response:
  { access_token, refresh_token, token_type, expires_in, api_domain, scope }
```

### 3. Token Storage

Extend `user_integrations` or add columns:

```sql
ALTER TABLE pehero.user_integrations
    ADD COLUMN access_token TEXT,
    ADD COLUMN refresh_token TEXT,
    ADD COLUMN token_expires_at TIMESTAMPTZ,
    ADD COLUMN oauth_scope TEXT;
```

### 4. Token Refresh

Access tokens expire in **60 minutes**. Refresh tokens expire after **60 days**
of non-use. On any 401 response:

```python
def _refresh_token(user_id: int) -> str:
    row = get_user_token(user_id)
    resp = httpx.post("https://oauth.pipedrive.com/oauth/token", data={
        "grant_type": "refresh_token",
        "refresh_token": row["refresh_token"],
        "client_id": PIPEDRIVE_CLIENT_ID,
        "client_secret": PIPEDRIVE_CLIENT_SECRET,
    })
    data = resp.json()
    # save new access_token + refresh_token + expires_at
    return data["access_token"]
```

### 5. API Call Changes

OAuth tokens use **Bearer auth** header instead of `api_token` query param:

```python
headers = {"Authorization": f"Bearer {access_token}"}
```

And can use the **v2 API** (which requires OAuth):

```
https://{api_domain}/api/v2/deals
```

### 6. Migration Path

1. Add `PIPEDRIVE_CLIENT_ID` / `PIPEDRIVE_CLIENT_SECRET` to `.env`
2. Add OAuth routes alongside existing token-paste routes
3. Existing personal API tokens keep working (v1 api_token auth)
4. New OAuth connections use Bearer auth + v2 API
5. `_resolve_credentials()` checks: OAuth token → personal token → .env fallback

### 7. Scopes

Request minimal scopes: `deals:full, persons:full, organizations:full,
activities:full, pipelines:full, notes:full, search:read`.

## Rate Limits

| Plan | Daily tokens | Burst (per 2s) |
|------|-------------|----------------|
| Lite | 30,000 | 20 req |
| Growth | 60,000 | 40 req |
| Premium | 150,000 | 100 req |

Token costs: GET single = 2, GET list = 20, POST/PATCH = 10, Search = 40. At Growth plan, ~3,000 entity creates/day or ~1,500 list fetches/day. Sufficient for PE deal flow.

---

## Pipeline 1: Deal Sourcing

### Stages

| # | Pipedrive Stage | PEHero `deal_stage` | Description |
|---|----------------|---------------------|-------------|
| 1 | Sourced | `sourced` | Company identified, initial data loaded |
| 2 | Screened | `screened` | Meets fund mandate, basic DD done |
| 3 | Outreach | `outreach` | Contact initiated (email/call) |
| 4 | Meeting | `meeting` | Management meeting scheduled/completed |
| 5 | LOI / Term Sheet | `loi` | Non-binding offer submitted |
| 6 | Due Diligence | `dd` | Full DD in progress |
| 7 | IC Approval | `ic` | Investment Committee review |
| 8 | Closing | `closing` | Legal docs, signing |

### Entity Mapping

| PEHero | Pipedrive | Direction |
|--------|-----------|-----------|
| `companies` | Organization | Bi-directional |
| Company contacts (new) | Person (linked to Org) | Bi-directional |
| Pipeline deal | Deal (in Deal Sourcing pipeline) | Bi-directional |
| Agent invocations | Activity (type: task) | PEHero → Pipedrive |
| Outreach emails | Activity (type: email) | PEHero → Pipedrive |
| Calls / meetings | Activity (type: call/meeting) | Pipedrive → PEHero |
| Deal brief / memo | Note (on Deal) | PEHero → Pipedrive |
| Data room files | File (on Deal) | Bi-directional |

### Custom Fields on Deals

| Field | Type | Source |
|-------|------|--------|
| Enterprise Value (€) | monetary | PEHero valuation |
| Revenue LTM (€) | monetary | PEHero companies |
| EBITDA LTM (€) | monetary | PEHero companies |
| EBITDA Margin (%) | double | Computed |
| EV/EBITDA Multiple | double | Computed |
| Revenue Growth (%) | double | PEHero financials |
| Sector | enum | PEHero companies |
| Sub-sector | varchar | PEHero companies |
| Country | enum | PEHero companies |
| Employee Count | double | PEHero companies |
| Ownership Type | enum | founder / family / pe_backed / vc_backed / corporate_carve_out |
| Seller Intent | enum | hot / warm / cold |
| PEHero Slug | varchar | Internal link key |

### Custom Fields on Organizations

| Field | Type |
|-------|------|
| Registry Code | varchar |
| NACE/CAEN Code | varchar |
| Founded Year | double |
| Website | varchar |
| PEHero Company ID | double |

---

## Pipeline 2: LP Fundraising

### Stages

| # | Pipedrive Stage | PEHero `stage` | Description |
|---|----------------|----------------|-------------|
| 1 | Prospect | `cold` | Identified as potential LP |
| 2 | Qualified | `qualified` | Mandate fit confirmed |
| 3 | Intro Meeting | `meeting` | First meeting / call |
| 4 | Due Diligence | `dd` | LP reviewing fund docs |
| 5 | Soft Commit | `committed` | Verbal commitment |
| 6 | Funded | `closed` | Capital called / received |
| 7 | Passed | `passed` | Declined (lost) |

### Entity Mapping

| PEHero | Pipedrive | Direction |
|--------|-----------|-----------|
| `investor_crm` | Person + Organization | Bi-directional |
| LP commitment | Deal (in LP Fundraising pipeline) | Bi-directional |
| Outreach emails | Activity (type: email) | PEHero → Pipedrive |
| Meetings / calls | Activity (type: call/meeting) | Pipedrive → PEHero |
| DDQ / fund docs | File (on Deal) | PEHero → Pipedrive |

### Custom Fields on LP Deals

| Field | Type |
|-------|------|
| Commitment Size (€) | monetary |
| LP Type | enum (pension / endowment / fof / family_office / sovereign / insurance / hnw) |
| Investment Focus | enum (buyout / growth / special_sits / multi_strategy) |
| AUM (€) | monetary |
| Geography Preference | varchar |
| Last Touch Date | date |
| Days Since Touch | double (computed) |
| Mandate Fit Score | double (0-100, computed by AI) |

---

## Outreach Agent — New Agent: `outreach_sequencer`

Inspired by [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills/tree/main/skills) cold-email and prospecting skills.

### Multi-Touch Sequence

| Touch | Day | Angle | Framework |
|-------|-----|-------|-----------|
| 1 — Initial | 0 | Value prop + specific data | SCQ (Situation-Complication-Question) |
| 2 — Follow-up | 3 | Different angle, new value | PAS (Problem-Agitate-Solution) |
| 3 — Social proof | 8 | Portfolio company case study | Star-Story-Solution |
| 4 — Market insight | 14 | Industry data / timing | BAB (Before-After-Bridge) |
| 5 — Breakup | 21 | 1-2-3 reply format, loss aversion | Mouse Trap |

### Personalization Levels

1. **Basic** — name, company, city (from PEHero DB)
2. **Segment** — industry-specific pain points mapped to sector
3. **Role** — founder vs broker vs intermediary (different tone)
4. **Individual** — recent news, revenue milestones, competitor M&A (from market signals + web search)

### PE-Specific Trigger Events (buying signals)

**Company triggers:**
- Revenue milestone (crossed €5M, €10M, €50M)
- Founder age/tenure > 20 years (succession planning)
- Competitor acquired recently (industry consolidation)
- Declining growth with strong base (operational improvement opportunity)
- No PE backing yet (platform opportunity)

**LP triggers:**
- New fund allocation announced
- Existing manager fund closing (capacity freed)
- CIO/investment team change
- Conference attendance
- Co-investment track record

### Email Frameworks for PE

**Deal sourcing (SCQ for founders):**
```
Subject: growth plans

Hi {first_name},

{Company} has grown to €{revenue}M in revenue with {employees} people
— that's impressive in {sub_sector}.

Companies at your stage often face a choice: self-fund the next phase
(slower but full control) or partner with someone who's scaled
{portfolio_example} from a similar starting point.

How are you thinking about the next 3-5 years?

{sender_name}
{fund_name}
```

**LP outreach (QVC for allocators):**
```
Subject: baltic pe

Hi {first_name},

Is {firm} still allocating to CEE mid-market buyout?

We're closing Fund {n} (€{target}M, {focus}) with 2.1x gross MOIC
on Fund {n-1}. Happy to send the DDQ if there's a fit.

{sender_name}
```

### Agent Spec

```python
AgentSpec(
    slug="outreach_sequencer",
    name="Outreach Sequencer",
    category="sourcing",
    icon="📨",
    prefix="sequence:",
    one_liner="Multi-touch outreach sequences for deal sourcing and LP fundraising.",
    description="Plans and drafts 5-email sequences for founder outreach or LP "
                "fundraising. Personalizes each touch using company financials, "
                "market signals, and portfolio track record. Logs activities to "
                "Pipedrive and tracks engagement.",
)
```

### Tools

| Tool | Purpose |
|------|---------|
| `pipedrive_create_deal` | Create deal in sourcing pipeline |
| `pipedrive_create_activity` | Log email/call/meeting |
| `pipedrive_update_deal` | Move deal stage, update fields |
| `pipedrive_search` | Find existing contacts/deals |
| `search_companies` | PEHero company lookup |
| `fetch_market_signals` | Recent news / triggers |
| `web_search` | External research for personalization |
| `retrieve_documents` | Prior correspondence / fund docs |

---

## Implementation Plan

### Phase 1: Pipedrive Client + Sync Infrastructure (2 days)

**Files:**

| File | Purpose |
|------|---------|
| `tools/pipedrive.py` | Thin httpx client: auth, CRUD for deals/persons/orgs/activities/notes, search, pagination |
| `db/migrations/pipedrive_sync.sql` | New table `pehero.pipedrive_sync` mapping PEHero IDs ↔ Pipedrive IDs |
| `utils/config.py` | Add `pipedrive_api_token`, `pipedrive_domain` to settings |

**`pehero.pipedrive_sync` schema:**
```sql
CREATE TABLE IF NOT EXISTS pehero.pipedrive_sync (
    id            BIGSERIAL PRIMARY KEY,
    entity_type   TEXT NOT NULL,       -- company | investor | deal | contact
    pehero_id     BIGINT NOT NULL,
    pipedrive_id  BIGINT NOT NULL,
    pipedrive_type TEXT NOT NULL,      -- organization | person | deal | activity
    last_synced   TIMESTAMPTZ NOT NULL DEFAULT now(),
    sync_hash     TEXT,                -- MD5 of synced fields, skip if unchanged
    UNIQUE(entity_type, pehero_id)
);
CREATE INDEX ON pehero.pipedrive_sync(pipedrive_id, pipedrive_type);
```

**`tools/pipedrive.py` — key functions:**
```python
# Client
pd_get(path, params) -> dict
pd_post(path, data) -> dict
pd_patch(path, data) -> dict
pd_delete(path) -> bool

# Deals
create_deal(title, pipeline_id, stage_id, org_id, person_id, value, custom_fields) -> int
update_deal(deal_id, **fields) -> dict
move_deal_stage(deal_id, stage_id) -> dict
search_deals(term) -> list[dict]

# Persons
create_person(name, org_id, emails, phones, custom_fields) -> int
update_person(person_id, **fields) -> dict
search_persons(term) -> list[dict]

# Organizations
create_organization(name, address, custom_fields) -> int
update_organization(org_id, **fields) -> dict
search_organizations(term) -> list[dict]

# Activities
create_activity(subject, type, deal_id, person_id, note, done) -> int
list_activities(deal_id) -> list[dict]

# Notes
create_note(content_html, deal_id, person_id) -> int

# Pipeline setup
ensure_pipelines() -> dict  # idempotent: create if missing, return stage_id map
```

### Phase 2: Company → Pipedrive Sync (1 day)

**Files:**

| File | Purpose |
|------|---------|
| `scripts/sync_pipedrive.py` | CLI: push companies to Pipedrive, pull updates back |
| `chat/routes.py` | Add sync trigger on deal stage change |

**Sync logic:**
1. For each company in PEHero with `deal_stage != NULL`:
   - Check `pipedrive_sync` for existing mapping
   - If missing: `create_organization` + `create_deal` + store mapping
   - If exists: compute hash of synced fields, skip if unchanged, else `update_deal`
2. Webhook handler (Phase 4) handles Pipedrive → PEHero direction

### Phase 3: Outreach Sequencer Agent (2 days)

**Files:**

| File | Purpose |
|------|---------|
| `agents/sourcing/outreach_sequencer.py` | New agent: plan + draft multi-touch sequences |
| `prompts/system/outreach_sequencer.md` | System prompt with sequence structure + frameworks |
| `tools/pipedrive.py` | Add `create_outreach_sequence` tool (batch-create activities with future due dates) |

**Agent workflow:**
1. User: `sequence: outreach for Baltic transline`
2. Agent resolves company → fetches financials, market signals, ownership info
3. Plans 5-touch sequence with angle rotation
4. Drafts all 5 emails with personalization
5. Creates Pipedrive activities with due dates (Day 0, 3, 8, 14, 21)
6. Returns sequence summary with email previews

### Phase 4: Webhook Receiver (1 day)

**Files:**

| File | Purpose |
|------|---------|
| `chat/webhooks.py` | FastHTML route `POST /api/webhooks/pipedrive` |
| `app.py` | Import webhook routes |

**Webhook events to handle:**

| Event | Action in PEHero |
|-------|-----------------|
| `deal.change` (stage) | Update `companies.deal_stage` |
| `deal.change` (status=won) | Mark deal as closed |
| `deal.change` (status=lost) | Mark deal as passed |
| `person.create` | Create contact in PEHero (future contacts table) |
| `activity.create` (type=call/meeting) | Log in PEHero, update `last_touch` |
| `note.create` | Store in PEHero for RAG indexing |

**Security:** Verify webhook via HTTP Basic Auth (configured on webhook creation) or by checking `meta.company_id`.

### Phase 5: LP CRM Sync (1 day)

**Extend Phase 1-2 patterns to `investor_crm` table:**
- LPs → Pipedrive Organizations (with LP-specific custom fields)
- LP contacts → Pipedrive Persons
- LP commitments → Deals in "LP Fundraising" pipeline
- Fundraising CRM agent gets `pipedrive_log_activity` tool to record touches

### Phase 6: Email Sending (future)

Start with draft-only (agents produce email text, user sends manually). When ready:

| Option | Pros | Cons |
|--------|------|------|
| **SendGrid** | Transactional API, tracking, templates | Separate service, deliverability setup |
| **Resend** | Modern API, React email templates | Newer, smaller ecosystem |
| **Gmail API** | Sends from user's address, Pipedrive auto-syncs | OAuth complexity, sending limits |

Regardless of provider, every sent email gets logged as a Pipedrive Activity (type: email) with the deal/person linked.

---

## File Summary

| File | New/Modified | Phase |
|------|-------------|-------|
| `tools/pipedrive.py` | New | 1 |
| `db/migrations/pipedrive_sync.sql` | New | 1 |
| `utils/config.py` | Modified | 1 |
| `.env.example` | Modified | 1 |
| `scripts/sync_pipedrive.py` | New | 2 |
| `agents/sourcing/outreach_sequencer.py` | New | 3 |
| `prompts/system/outreach_sequencer.md` | New | 3 |
| `agents/registry.py` | Modified (add spec) | 3 |
| `agents/router.py` | Modified (add keywords) | 3 |
| `chat/webhooks.py` | New | 4 |
| `app.py` | Modified (import webhooks) | 4 |
| `tools/capital.py` | Modified (add PD tools) | 5 |
| `prompts/system/fundraising_crm.md` | Modified | 5 |

---

## Testing

```bash
# Smoke test: Pipedrive client (no API calls, mocked)
pytest -q tests/test_pipedrive.py

# Integration test (requires PIPEDRIVE_API_TOKEN)
python -m scripts.sync_pipedrive --dry-run

# Full sync
python -m scripts.sync_pipedrive --push

# Webhook test
curl -X POST http://localhost:5058/api/webhooks/pipedrive \
  -H "Content-Type: application/json" \
  -d '{"meta":{"action":"change","entity":"deal","entity_id":1},"data":{"stage_id":2}}'
```

---

## References

- Pipedrive API v2: `https://developers.pipedrive.com/docs/api/v2`
- Pipedrive API v1 (notes, files, mail): `https://developers.pipedrive.com/docs/api/v1`
- Webhooks: `https://developers.pipedrive.com/docs/api/v1/Webhooks`
- Outreach patterns: [marketingskills/skills/cold-email](https://github.com/coreyhaines31/marketingskills/tree/main/skills/cold-email)
- Email frameworks: SCQ, PAS, BAB, QVC, Mouse Trap (Lavender)
