# PEHero User Guide

## Your Private Equity AI Agent Squad

*One chat interface, every PE workflow — sourcing through exit.*

**pehero.chat**

---

## Contents

**Getting Started** · Sign in, first chat, agent routing

**Chat** · 3-pane layout, agent categories, tables, charts, memo export

**Pipeline** · Kanban board, triage scoring, deal workspace, risk register, milestones

**Companies** · Fuzzy search, sector filters, company detail

**Investors** · Family office & investor prospecting, wealth data, company links

**Portfolio** · Dashboard, analytics, KPIs — 3-tab submenu

**Valuation** · DCF, comps, precedent, LBO simulator with WACC calculator

**Data Room** · Upload, index, RAG-powered document search

**Analytics** · Text-to-SQL, auto-charting, schema-aware queries

**Instructions** · Live-edit agent prompts — no redeploy needed

**Training** · PE Hero RPG game for deal-making practice

**Configuration** · Currency, language, integrations, profile

---

## Getting Started

![Chat interface](screenshots/07-chat-empty.png)

1. **Open the app** at [pehero.chat/app](https://pehero.chat/app)
2. **Sign in** with Google or email/password (bottom of the left pane)
3. **Type a prompt** in the chat input — PEHero routes to the right specialist agent automatically
4. **Browse agents** in the left pane under the 5 PE workflow categories

> First time? Try: *"Triage Northwind Systems for our fund"* — the Deal Triage agent runs a full strategic fit analysis.

---

## Chat — 3-Pane Layout

![Chat with triage response](screenshots/08-chat-triage.png)

The main interface has three panes:

- **Left pane** — sessions, agent browser (5 categories), workspace navigation, configuration
- **Centre pane** — conversation with streaming responses, inline tables, charts
- **Right pane** — live PE news feed (PE Hub, Buyouts Insider, PE International, FT, Bloomberg)

### Agent routing

Two ways to invoke a specialist:

- **Prefix** — type `triage:`, `lbo:`, `memo:` etc. before your question
- **Auto** — describe what you need in plain English; the router picks the best agent

---

## Chat — Agent Categories

PEHero's specialist agents cover every stage of the PE deal lifecycle:

| Category | Agents | Example Prefixes |
|----------|--------|-----------------|
| **Sourcing** | Market Scanner, Deal Triage, Comp Finder, Owner Intent, Outreach, LOI Writer, Deal Teaser | `scan:`, `triage:`, `comps:`, `loi:` |
| **Underwriting** | LTM Normalizer, LBO Model, Pro Forma, Debt Stack, Return Metrics | `ltm:`, `lbo:`, `pf:`, `debt:` |
| **Diligence** | VDR Auditor, Contract Abstractor, Legal, Ops DD, ESG Risk | `vdr:`, `contracts:`, `legal:` |
| **Capital** | IC Memo Writer, LP Update, Fundraising CRM | `memo:`, `lp:`, `crm:` |
| **Portfolio Ops** | Pricing Optimizer, EBITDA Variance, Value Creation, Customer Churn | `pricing:`, `opex:`, `vcb:`, `churn:` |

---

## Chat — Tables & Data

![Table with export options](screenshots/21-chat-table-truncated.png)

When agents return tabular data (financials, comps, models), the table appears inline with:

- **First 5 rows** shown — click **See more** to expand
- **Copy CSV** — copy to clipboard
- **Download CSV** — save as .csv file
- **Download XLS** — save as formatted .xlsx with styled headers
- **Visualize** — auto-generate a Plotly chart from the table

### Chart types (auto-selected)

- Time series <20 points → **bar chart**
- Time series 20+ points → **area/line chart**
- ≤8 categories → **pie chart**
- >8 categories → **treemap**
- Multiple numeric columns → **grouped bar chart**

---

## Chat — Memo Export

![Memo export buttons](screenshots/24-chat-memo-exports.png)

For memo-type agents (IC Memo, Deal Teaser, LP Update, LOI, Outreach Email):

- **Preview PDF** — opens formatted PDF in a new tab
- **Download PDF** — saves the PDF
- **Download Word** — saves .docx with headings, tables, bullets

### Share & Copy

- **Copy** — copy the full chat to clipboard (markdown)
- **Share** — generate a read-only link anyone can view without signing in

---

## Pipeline — Kanban Board

![Pipeline kanban](screenshots/11-pipeline-kanban.png)

The pipeline board shows all companies across deal stages:

**Sourced → Screened → LOI → Diligence → IC → Signed → Closed → Held → Exited**

- Filter by **sector** or **ownership** type
- Cards sorted by **triage score** (highest priority first)
- Each card shows revenue, EBITDA, EV, multiple, seller-intent dot, and **triage badge**

### Triage scoring

Every company gets a weighted priority score (1.0–5.0):

- **40%** Impact · **30%** Strategic fit · **20%** Feasibility · **10%** Urgency
- Badges: **High** (≥4.0, green) · **Medium** (≥3.0, amber) · **Low** (<3.0, grey)

---

## Pipeline — Deal Workspace

![Deal workspace](screenshots/13-pipeline-deal.png)

Click any card to open the deal workspace:

- **Centre** — per-deal chat (ask agents about this specific company)
- **Right pane** — deal brief with live data:

### Deal brief sections

- **Company info** — sector, sub-sector, stage, triage score, HQ, employees, founded, ownership
- **LTM financials** — revenue, EBITDA, margin, ask EV and multiple
- **Top customers** — largest contracts by annual value
- **DD findings** — severity-coded results from VDR Auditor
- **Risk register** — P×I scored risks with category and mitigation
- **Milestones** — progress bars, due dates, owner, status (done/overdue/open/blocked)

---

## Companies

![Company search](screenshots/14-companies.png)

Search your entire company database at `/app/companies`:

- **Fuzzy name search** — partial matching
- **Sector filter** — dropdown with all sectors
- Results show revenue, EBITDA, employees, deal stage
- Click any company to jump to its deal workspace

---

## Investors

Investor prospecting at `/app/investors`:

- **2,500+ persons** across Estonia, Lithuania, and Latvia
- Search by name, filter by country
- Each person card shows **wealth rank**, company links, ownership stakes
- Click any person for detail view with full company portfolio
- Data from Baltic business registries and wealth rankings

---

## Portfolio — Dashboard

The Portfolio section (`/app/portfolio`) has a **3-tab submenu**: Dashboard, Analytics, KPIs.

### Dashboard tab

- **Value Bridge** — waterfall chart showing NAV progression (entry → growth → margin → multiple → exit)
- **Portfolio Health** — donut chart of margin bands (healthy >20%, watch 10-20%, risk <10%)
- **KPI cards** — total companies, total NAV, average MOIC, average hold period
- **Top holdings** — ranked by NAV with inline sparkline bars

---

## Portfolio — Analytics

### Analytics tab

- **Bubble chart** — companies plotted by revenue (x) vs EBITDA margin (y), sized by EV
- **Heatmap** — sector × deal-stage matrix showing company counts
- **Sector allocation** — table with company count, total revenue, avg margin per sector
- **Full holdings table** — sortable list with all portfolio companies and key metrics

---

## Portfolio — KPIs

### KPIs tab

- **Revenue & EBITDA trends** — annual aggregated lines from monthly financial data
- **Margin trends** — EBITDA margin over time vs 20% target line (dashed)
- **Growth trends** — year-over-year revenue growth as bar chart

All charts are interactive (Plotly) — hover for values, zoom, download as PNG.

---

## PE Valuation Simulator

![Valuation simulator](screenshots/21-valuation-full.png)

Interactive company valuation with four methods at `/app/valuation`:

1. **Select a company** from the dropdown (type to search)
2. The simulator loads financials and auto-selects an industry benchmark

### Four valuation methods

- **EV/Revenue** — revenue × industry sales multiple (96 Damodaran industries)
- **EV/EBITDA** — EBITDA × industry EV/EBITDA multiple
- **EV/EBIT** — EBIT × industry EV/EBIT multiple
- **DCF** — configurable revenue growth, WACC, terminal growth, projection years, CapEx, tax rate

Each method has **interactive sliders** — adjust any parameter, all valuations update instantly.

---

## Valuation — WACC & Equity Bridge

![WACC calculator](screenshots/22-valuation-wacc-chart.png)

### WACC Calculator

Build the discount rate from first principles: risk-free rate, levered beta, market risk premium, country risk premium, size premium, D/E ratio, cost of debt, tax rate. Click **Apply to DCF**.

### Equity Bridge

Derive equity value: Average EV + Cash − Debt − Minority Interest.

### Comparison chart

Interactive Plotly bar chart showing all four valuations side by side with dashed average line.

### XLS Export

Multi-sheet Excel workbook: Valuation Summary, Multiples, DCF projections, WACC components.

---

## Data Room

![Data room](screenshots/24-data-room.png)

Upload and manage deal documents at `/app/dataroom`:

- Upload PDFs, Word docs, spreadsheets, presentations, images
- **Virtual folder tree** grouped by company
- Download or delete any file
- Documents **automatically indexed into RAG** — agents can search and answer questions about your uploads

---

## Analytics

![Analytics chart](screenshots/15-analytics-stages.png)

Ask questions in plain English, get charts:

- *"Top 10 companies by revenue"*
- *"Average EBITDA margin by sector"*
- *"Company count by deal stage"*
- *"Revenue distribution across Baltic countries"*

The system translates your question to **read-only SQL**, runs it against the database, and auto-picks the chart type. The underlying SQL is shown for auditability.

---

## Instructions

![Instructions editor](screenshots/18-instructions-edit.png)

Edit any agent's system prompt live at `/app/instructions`:

- Changes take effect on the **very next conversation**
- No restarts or deploys needed
- Encode your firm's house style, memo format, or diligence approach
- Shared across your team — all users see the same prompts

---

## Copilot

![Copilot on pipeline](screenshots/25-copilot-pipeline.png)

Every workspace page includes a **Copilot** AI assistant in the right pane.

### Context-aware

The Copilot automatically receives page context:

- **Pipeline** — stage counts, filters, total companies
- **Valuation** — loaded company financials, sector, employees
- **Analytics** — schema capabilities, sample queries
- **Companies** — current search, sector filter
- **Portfolio** — KPI summaries, holdings data

Each page has its own copilot session — navigate away and come back, your conversation is preserved.

---

## Training — PE Hero Game

The PE Hero RPG game at `/app/training` lets you practice PE deal-making:

- **Pick a character** — each has different strengths (analytical, relationship, operations)
- **Navigate real deal scenarios** using companies from the database
- **Make decisions** — bid/pass, negotiate terms, manage portfolio
- **Earn scores** — scored on deal quality, timing, and strategic fit

An engaging way to learn PE workflows and practice decision-making.

---

## Configuration

### Currency

Switch between **EUR** (default), **GBP**, and **USD**. All monetary figures follow your preference.

### Language

11 languages: English, Estonian, Lithuanian, Latvian, Finnish, Swedish, Norwegian, Danish, French, German, Polish. Agents respond in your chosen language.

### Profile & Deal Preferences

At `/app/profile`, set your deal criteria: size range, revenue/EBITDA ranges, preferred sectors, deal types, and geographies. Enable/disable email notifications for new deals and weekly digests.

### Integrations

At `/app/integrations`: Pipedrive CRM sync, Baltic registry connections (Estonia, Lithuania, Latvia), web search providers (Tavily, EXA).

---

## Data Coverage

| Country | Companies | Source |
|---------|-----------|--------|
| Estonia | 363+ | ariregister.rik.ee |
| Lithuania | 1,000+ | rekvizitai.vz.lt |
| Latvia | 500+ | lursoft.lv |
| **Total** | **1,800+** | |

Sectors: Healthcare, Software, Industrials, Financial Services, Business Services, Consumer.

BYOD — bring your own data. Upload documents to the Data Room, and PEHero's agents can search and reason over your proprietary deal files.

---

## Getting Help

- **In-app**: `/app/help` — this user guide rendered in the browser
- **Copilot**: ask any question on any workspace page
- **Support**: contact@pehero.chat

*PEHero — your Private Equity AI Agent Squad.*
