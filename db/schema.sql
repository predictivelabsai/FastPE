-- PEHero OLTP schema. Idempotent. Always qualify with `pehero.` —
-- never rely on `search_path`.

CREATE SCHEMA IF NOT EXISTS pehero;

-- ── users + sessions ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pehero.users (
    id          BIGSERIAL PRIMARY KEY,
    email       TEXT        NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pehero.chat_sessions (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT      NOT NULL REFERENCES pehero.users(id) ON DELETE CASCADE,
    agent_slug   TEXT,
    title        TEXT,
    share_token  TEXT        UNIQUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chat_sessions_user_idx ON pehero.chat_sessions(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS pehero.chat_messages (
    id          BIGSERIAL PRIMARY KEY,
    session_id  BIGINT NOT NULL REFERENCES pehero.chat_sessions(id) ON DELETE CASCADE,
    role        TEXT   NOT NULL,   -- user | assistant | tool | system
    content     TEXT   NOT NULL,
    tool_calls  JSONB,
    agent_slug  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chat_messages_session_idx ON pehero.chat_messages(session_id, id);

-- ── portfolio companies (deal universe) ───────────────────────────────
-- Each row is either a target in the pipeline or a held portfolio company.
CREATE TABLE IF NOT EXISTS pehero.companies (
    id             BIGSERIAL PRIMARY KEY,
    slug           TEXT UNIQUE NOT NULL,
    name           TEXT NOT NULL,
    hq_city        TEXT,
    hq_state       TEXT,
    country        TEXT,
    sector         TEXT NOT NULL,    -- software | healthcare | industrials | consumer | business_services | financial_services
    sub_sector     TEXT,
    website        TEXT,
    founded_year   INTEGER,
    employees      INTEGER,
    revenue_ltm    NUMERIC(14,2),       -- latest 12 months revenue, USD
    ebitda_ltm     NUMERIC(14,2),
    ebitda_margin  NUMERIC(5,2),
    growth_rate    NUMERIC(5,2),        -- LTM YoY revenue growth, pct
    ownership      TEXT,                -- founder | family | pe_backed | vc_backed | public | corporate_carve_out
    deal_stage     TEXT,                -- sourced | screened | loi | diligence | ic | signed | closed | held | exited | passed
    deal_type      TEXT,                -- platform | add_on | carve_out | minority | recap | secondary
    enterprise_value NUMERIC(14,2),     -- last mark or asking EV, USD
    ask_multiple   NUMERIC(6,2),        -- EV / EBITDA
    fund_id        BIGINT,              -- soft ref: pehero.funds(id)
    description    TEXT,
    seller_intent  TEXT,                -- cold | warm | hot
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS companies_sector_idx  ON pehero.companies(sector);
CREATE INDEX IF NOT EXISTS companies_stage_idx   ON pehero.companies(deal_stage);
CREATE INDEX IF NOT EXISTS companies_geo_idx     ON pehero.companies(country, hq_state);

-- ── funds (GP side: what's deploying) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS pehero.funds (
    id             BIGSERIAL PRIMARY KEY,
    slug           TEXT UNIQUE NOT NULL,
    name           TEXT NOT NULL,
    vintage        INTEGER,
    size_usd       NUMERIC(14,2),
    strategy       TEXT,              -- lower_mid_buyout | mid_buyout | growth | special_situations
    dry_powder     NUMERIC(14,2),
    called_pct     NUMERIC(5,2),
    invested_pct   NUMERIC(5,2),
    net_irr        NUMERIC(5,2),
    net_moic       NUMERIC(5,2),
    dpi            NUMERIC(5,2),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── cap tables (equity ownership snapshots) ───────────────────────────
CREATE TABLE IF NOT EXISTS pehero.cap_tables (
    id           BIGSERIAL PRIMARY KEY,
    company_id   BIGINT      NOT NULL REFERENCES pehero.companies(id) ON DELETE CASCADE,
    as_of_date   DATE        NOT NULL,
    holders      JSONB       NOT NULL,    -- [{holder, class, shares, fd_pct, capital_in, liquidation_pref, last_round}]
    total_shares BIGINT,
    post_money   NUMERIC(14,2),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, as_of_date)
);

-- ── historical financials (monthly, LTM-building block) ───────────────
CREATE TABLE IF NOT EXISTS pehero.financials (
    id             BIGSERIAL PRIMARY KEY,
    company_id     BIGINT      NOT NULL REFERENCES pehero.companies(id) ON DELETE CASCADE,
    month          DATE        NOT NULL,   -- first-of-month
    revenue        NUMERIC(14,2),
    cogs           NUMERIC(14,2),
    gross_profit   NUMERIC(14,2),
    opex           JSONB,                  -- {sales, marketing, rnd, ga, other}
    ebitda         NUMERIC(14,2),
    adjustments    JSONB,                  -- non-recurring items, owner add-backs
    adj_ebitda     NUMERIC(14,2),
    arr            NUMERIC(14,2),          -- for SaaS/recurring
    gross_retention NUMERIC(5,2),
    net_retention  NUMERIC(5,2),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, month)
);
CREATE INDEX IF NOT EXISTS financials_company_month_idx ON pehero.financials(company_id, month DESC);

-- ── material contracts (customers, suppliers, key employees) ──────────
CREATE TABLE IF NOT EXISTS pehero.contracts (
    id           BIGSERIAL PRIMARY KEY,
    company_id   BIGINT NOT NULL REFERENCES pehero.companies(id) ON DELETE CASCADE,
    counterparty TEXT,
    contract_type TEXT,     -- customer_msa | supplier | employment | license | lease | loan | other
    start_date   DATE,
    end_date     DATE,
    annual_value NUMERIC(14,2),
    auto_renew   BOOLEAN,
    change_of_control_trigger BOOLEAN,
    termination_notice_days INTEGER,
    exclusivity  BOOLEAN,
    status       TEXT,         -- active | expired | pending | terminated
    doc_path     TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS contracts_company_idx      ON pehero.contracts(company_id);
CREATE INDEX IF NOT EXISTS contracts_counterparty_idx ON pehero.contracts(counterparty);

-- ── transaction comps (M&A deal comparables) ──────────────────────────
CREATE TABLE IF NOT EXISTS pehero.transaction_comps (
    id             BIGSERIAL PRIMARY KEY,
    company_id     BIGINT REFERENCES pehero.companies(id) ON DELETE SET NULL,
    target_name    TEXT,
    acquirer       TEXT,
    sector         TEXT,
    sub_sector     TEXT,
    country        TEXT,
    announce_date  DATE,
    close_date     DATE,
    enterprise_value NUMERIC(14,2),
    revenue        NUMERIC(14,2),
    ebitda         NUMERIC(14,2),
    ev_revenue     NUMERIC(6,2),
    ev_ebitda      NUMERIC(6,2),
    deal_type      TEXT,             -- pe_buyout | strategic | ipo | growth
    source         TEXT
);
CREATE INDEX IF NOT EXISTS txn_comps_sector_idx ON pehero.transaction_comps(sector, announce_date DESC);

-- ── trading comps (public company multiples) ──────────────────────────
CREATE TABLE IF NOT EXISTS pehero.trading_comps (
    id             BIGSERIAL PRIMARY KEY,
    company_id     BIGINT REFERENCES pehero.companies(id) ON DELETE SET NULL,
    ticker         TEXT,
    peer_name      TEXT,
    sector         TEXT,
    market_cap     NUMERIC(14,2),
    ev             NUMERIC(14,2),
    revenue_ltm    NUMERIC(14,2),
    ebitda_ltm     NUMERIC(14,2),
    ev_revenue     NUMERIC(6,2),
    ev_ebitda      NUMERIC(6,2),
    rev_growth     NUMERIC(5,2),
    ebitda_margin  NUMERIC(5,2),
    as_of_date     DATE,
    source         TEXT
);
CREATE INDEX IF NOT EXISTS trading_comps_sector_idx ON pehero.trading_comps(sector);

-- ── LBO models + sensitivity ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pehero.lbo_models (
    id           BIGSERIAL PRIMARY KEY,
    company_id   BIGINT NOT NULL REFERENCES pehero.companies(id) ON DELETE CASCADE,
    name         TEXT,
    assumptions  JSONB NOT NULL,  -- {hold_years, entry_multiple, entry_ev, ebitda_growth, margin_exp, capex_pct, wc_days, exit_multiple, tax_rate}
    projections  JSONB NOT NULL,  -- [{year, revenue, ebitda, capex, fcf, debt_paydown, net_debt}]
    returns      JSONB NOT NULL,  -- {irr, moic, levered_irr, unlevered_irr, equity_multiple, dscr_min}
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── debt stacks for LBO capital structure ─────────────────────────────
CREATE TABLE IF NOT EXISTS pehero.debt_stacks (
    id           BIGSERIAL PRIMARY KEY,
    company_id   BIGINT NOT NULL REFERENCES pehero.companies(id) ON DELETE CASCADE,
    name         TEXT,
    tranches     JSONB NOT NULL,  -- [{name, lender, type, amount, rate, amort_years, term_years, io_years, covenants}]
    total_debt   NUMERIC(14,2),
    total_leverage NUMERIC(5,2),     -- debt / EBITDA turns
    dscr         NUMERIC(5,2),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── LP CRM ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pehero.investor_crm (
    id            BIGSERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    firm          TEXT,
    lp_type       TEXT,          -- pension | endowment | fof | family_office | sovereign | insurance | hnw
    email         TEXT,
    commitment_size NUMERIC(14,2),
    stage         TEXT,          -- cold | qualified | meeting | dd | committed | closed | passed
    focus         TEXT,          -- buyout | growth | special_sits | multi_strategy
    geography     TEXT,
    aum           NUMERIC(14,2),
    last_touch    DATE,
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS crm_stage_idx ON pehero.investor_crm(stage);

-- ── market signals (sector heat, multiples, fundraising env) ──────────
CREATE TABLE IF NOT EXISTS pehero.market_signals (
    id           BIGSERIAL PRIMARY KEY,
    sector       TEXT NOT NULL,
    sub_sector   TEXT,
    metric       TEXT NOT NULL,   -- ev_ebitda_median | ev_revenue_median | deal_volume | fundraising_close_time | exit_multiples | hold_period
    value        NUMERIC(14,4),
    as_of_date   DATE NOT NULL,
    source       TEXT,
    UNIQUE (sector, sub_sector, metric, as_of_date)
);
CREATE INDEX IF NOT EXISTS market_signals_lookup_idx ON pehero.market_signals(sector, metric, as_of_date DESC);

-- ── diligence findings ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pehero.dd_findings (
    id           BIGSERIAL PRIMARY KEY,
    company_id   BIGINT NOT NULL REFERENCES pehero.companies(id) ON DELETE CASCADE,
    agent_slug   TEXT NOT NULL,
    category     TEXT NOT NULL,   -- legal | tax | commercial | financial | operational | esg | it | hr
    severity     TEXT NOT NULL,   -- info | low | medium | high | critical
    summary      TEXT NOT NULL,
    detail       TEXT,
    source_doc   TEXT,
    source_page  INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dd_company_idx ON pehero.dd_findings(company_id, severity);

-- ── board / portfolio KPIs (post-close operational data) ──────────────
CREATE TABLE IF NOT EXISTS pehero.portfolio_kpis (
    id           BIGSERIAL PRIMARY KEY,
    company_id   BIGINT NOT NULL REFERENCES pehero.companies(id) ON DELETE CASCADE,
    month        DATE NOT NULL,
    kpi          TEXT NOT NULL,        -- arr | churn | cac | ltv | headcount | nps | gross_margin | ebitda_budget_variance
    value        NUMERIC(14,4),
    budget       NUMERIC(14,4),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, month, kpi)
);
CREATE INDEX IF NOT EXISTS portfolio_kpis_company_idx ON pehero.portfolio_kpis(company_id, month DESC);

-- ── prompt versions (audit trail for system prompts) ──────────────────
CREATE TABLE IF NOT EXISTS pehero.prompt_versions (
    id          BIGSERIAL PRIMARY KEY,
    slug        TEXT        NOT NULL,
    content     TEXT        NOT NULL,
    changed_by  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS prompt_versions_slug_idx ON pehero.prompt_versions(slug, id DESC);

-- ── data room (document uploads) ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS pehero.data_room (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT      REFERENCES pehero.users(id) ON DELETE CASCADE,
    company_slug TEXT,
    filename     TEXT        NOT NULL,
    content_type TEXT        NOT NULL DEFAULT 'application/octet-stream',
    size_bytes   INTEGER,
    data         BYTEA       NOT NULL,
    uploaded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS data_room_user_idx ON pehero.data_room(user_id, uploaded_at DESC);

-- ── agent invocation log ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pehero.agent_invocations (
    id           BIGSERIAL PRIMARY KEY,
    session_id   BIGINT REFERENCES pehero.chat_sessions(id) ON DELETE CASCADE,
    agent_slug   TEXT NOT NULL,
    input        TEXT,
    tools_used   TEXT[],
    duration_ms  INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agent_invocations_session_idx ON pehero.agent_invocations(session_id, created_at DESC);

-- ── Pipedrive CRM sync ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pehero.pipedrive_sync (
    id             BIGSERIAL PRIMARY KEY,
    entity_type    TEXT NOT NULL,          -- company | investor | deal | contact
    pehero_id      BIGINT NOT NULL,
    pipedrive_id   BIGINT NOT NULL,
    pipedrive_type TEXT NOT NULL,          -- organization | person | deal | activity
    last_synced    TIMESTAMPTZ NOT NULL DEFAULT now(),
    sync_hash      TEXT,
    UNIQUE(entity_type, pehero_id)
);
CREATE INDEX IF NOT EXISTS pd_sync_pd_idx ON pehero.pipedrive_sync(pipedrive_id, pipedrive_type);

CREATE TABLE IF NOT EXISTS pehero.outreach_sequences (
    id             BIGSERIAL PRIMARY KEY,
    company_id     BIGINT REFERENCES pehero.companies(id) ON DELETE CASCADE,
    investor_id    BIGINT REFERENCES pehero.investor_crm(id) ON DELETE CASCADE,
    sequence_type  TEXT NOT NULL,          -- deal_sourcing | lp_fundraising
    status         TEXT NOT NULL DEFAULT 'active',  -- active | paused | completed
    touches        JSONB NOT NULL DEFAULT '[]',     -- [{day, subject, body, framework, sent, sent_at}]
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS outreach_seq_company_idx ON pehero.outreach_sequences(company_id);
CREATE INDEX IF NOT EXISTS outreach_seq_investor_idx ON pehero.outreach_sequences(investor_id);

-- ── User integrations (per-user API tokens) ─────────────────────────
CREATE TABLE IF NOT EXISTS pehero.user_integrations (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT      NOT NULL REFERENCES pehero.users(id) ON DELETE CASCADE,
    provider    TEXT        NOT NULL,     -- pipedrive | hubspot | salesforce | ...
    api_token   TEXT        NOT NULL,
    domain      TEXT,                     -- e.g. "predictivelabsltd" for Pipedrive
    metadata    JSONB       DEFAULT '{}', -- extra provider-specific config
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, provider)
);
