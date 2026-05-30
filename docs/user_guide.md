# PEHero User Guide

Your Private Equity AI Agent Squad — one chat interface, every PE workflow.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Chat](#chat)
- [Pipeline](#pipeline)
- [Company Search](#company-search)
- [PE Valuation Simulator](#pe-valuation-simulator)
- [Data Room](#data-room)
- [Analytics](#analytics)
- [Instructions](#instructions)
- [Copilot](#copilot)
- [News Feed](#news-feed)
- [Configuration](#configuration)
- [Data Coverage](#data-coverage)

---

## Getting Started

1. **Open the app** at [pehero.chat/app](https://pehero.chat/app)
2. **Sign in** with your email (click the Sign in button at the bottom of the left pane)
3. **Type a prompt** in the chat input — PEHero automatically routes to the right specialist agent

---

## Chat

The main interface is a 3-pane layout:

- **Left pane** — sessions, agent browser, workspace navigation, configuration
- **Centre pane** — the conversation with streaming responses, inline tables, and charts
- **Right pane** — live PE industry news feed (PE Hub, Buyouts Insider, PE International)

### Using Agents

PEHero has specialist agents across 5 PE workflow categories. You can invoke them in two ways:

1. **Prefix routing** — type a prefix like `triage:`, `lbo:`, `memo:` followed by your question
2. **Auto routing** — just describe what you need in plain English and the router picks the right agent

### Agent Categories

| Category | Agents | Example Prefix |
|----------|--------|----------------|
| **Sourcing** | Market Scanner, Deal Triage, Comp Finder, Owner Intent | `scan:`, `triage:`, `comps:` |
| **Underwriting** | LTM Normalizer, LBO Model Builder, Pro Forma, Debt Stack, Return Metrics | `ltm:`, `lbo:`, `pf:`, `debt:` |
| **Diligence** | VDR Auditor, Contract Abstractor, Legal & Regulatory, Ops DD, ESG Risk | `vdr:`, `contracts:`, `legal:` |
| **Capital** | IC Memo Writer, Deal Teaser, LP Update, Fundraising CRM, Outreach Email, LOI Writer | `memo:`, `teaser:`, `lp:`, `crm:`, `email:`, `loi:` |
| **Portfolio Ops** | Pricing Optimizer, EBITDA Variance, Value Creation, Customer Churn | `pricing:`, `opex:`, `vcb:`, `churn:` |

### Tables & Data

When agents return tabular data (financials, comps, models), the table appears inline in the chat with:

- **First 5 rows** shown by default — click **See more** to expand
- **Copy CSV** — copy the table to clipboard
- **Download CSV** — save as .csv file
- **Download XLS** — save as formatted .xlsx with styled headers
- **Visualize** — auto-generate a chart (bar, area, pie, treemap) from the table data

### Charts

Click **Visualize** on any table to render an interactive Plotly chart:

- Time series with <20 data points — **bar chart**
- Time series with 20+ points — **area/line chart**
- Categorical data with 8 or fewer items — **pie chart**
- Categorical data with more than 8 items — **treemap**
- Multiple numeric columns — **grouped bar chart**

### Memo & Document Export

For memo-type agents (IC Memo, Deal Teaser, LP Update, LOI, Outreach Email), three export buttons appear:

- **Preview PDF** — opens a formatted PDF in a new tab
- **Download PDF** — saves the PDF file
- **Download Word** — saves a formatted .docx with headings, tables, and bullets

---

## Pipeline

The pipeline kanban board shows all companies across deal stages:

**Sourced — Screened — LOI — Diligence — IC — Signed — Closed — Held — Exited**

- Filter by **sector** or **ownership** type
- Click any card to open the **deal workspace** with a brief on the right and per-deal chat in the centre
- Each card shows revenue, EBITDA, EV, multiple, and a seller-intent heat dot

---

## Company Search

Search your entire company database at `/app/companies`:

- **Fuzzy name search** — partial matching via ILIKE
- **Sector filter** — dropdown with all available sectors
- Results show revenue, EBITDA, employees, and deal stage
- Click any company to jump to its deal workspace

---

## PE Valuation Simulator

Interactive company valuation with four methods, WACC calculator, equity bridge, and XLS export.

### Getting Started

1. Open **PE Valuation Simulator** from the left-pane Workspace menu
2. **Select a company** from the dropdown (or search by name)
3. The simulator loads the company's financials and auto-selects an industry benchmark

### Valuation Methods

The simulator computes enterprise value using four approaches:

- **EV/Revenue** — revenue times an industry-specific sales multiple (Damodaran data, 96 industries)
- **EV/EBITDA** — EBITDA times the industry EV/EBITDA multiple
- **EV/EBIT** — EBIT times the industry EV/EBIT multiple
- **DCF** — discounted cash flow with configurable revenue growth, WACC, terminal growth, projection years, CapEx rate, and tax rate

Each method has interactive sliders — adjust any parameter and all valuations update instantly.

### Industry Benchmarks

Select from 96 Damodaran industry categories. Changing the industry auto-fills the revenue, EBITDA, and EBIT multiples with real-world benchmarks.

### WACC Calculator

Build up the discount rate from first principles:

- **Risk-Free Rate** — government bond yield
- **Levered Beta** — industry beta from Damodaran
- **Market Risk Premium** — historical equity premium
- **Country Risk Premium** — Damodaran country CRP
- **Size Premium** — Duff & Phelps size study
- **D/E Ratio** — debt-to-equity
- **Cost of Debt** — pre-tax borrowing rate
- **Tax Rate** — marginal corporate tax rate

Click **Apply to DCF** to push the calculated WACC into the DCF model.

### Equity Bridge

Derive equity value from the average enterprise value:

- **(+) Cash** — add cash on hand
- **(-) Debt** — subtract total debt
- **(-) Minority Interest** — adjust for minority stakes

### Comparison Chart

An interactive Plotly bar chart shows all four valuations side by side, with a dashed average line.

### XLS Export

Click **Download XLS** to generate a multi-sheet Excel workbook:

- **Valuation Summary** — all methods + equity bridge
- **Multiples** — metric, multiple, and enterprise value detail
- **DCF** — assumptions + year-by-year FCF projections + terminal value
- **WACC** — full component breakdown with sources

---

## Data Room

Upload and manage deal documents at `/app/dataroom`:

- Upload PDFs, Word docs, spreadsheets, presentations, and images
- Documents are organized in a **virtual folder tree** grouped by company
- Download or delete any uploaded file
- Uploaded documents are **automatically indexed into RAG** — agents can search and answer questions about your uploaded documents

---

## Analytics

Ask questions in plain English and get charts:

- "Top 10 companies by revenue"
- "Average EBITDA margin by sector"
- "Monthly revenue trend for DR VET"
- "Company count by deal stage"

The system translates your question to SQL, runs it read-only against the database, and picks the right chart type automatically. The underlying SQL query is shown for auditability.

---

## Instructions

Edit any agent's system prompt live at `/app/instructions`:

- Changes take effect on the very next conversation
- No restarts or deploys needed
- Perfect for encoding your firm's house style, memo format, or diligence approach

---

## Copilot

Every workspace page (Pipeline, Companies, Analytics, Valuation, Data Room, Instructions) includes a **Copilot** AI assistant in the right pane. Click the **Copilot** button in the top-right header to open it.

### What the Copilot knows

The Copilot automatically receives context from the page you're on:

- **Pipeline**: stage counts, active filters, total companies
- **Valuation**: loaded company financials (revenue, EBITDA, margin, growth), sector, employees
- **Analytics**: schema capabilities, sample queries
- **Companies**: current search and sector filter
- **Data Room**: uploaded files and folder structure

### Example questions

- On **Valuation** with a company loaded: "If I bought this company, how do I increase value?"
- On **Pipeline**: "Which healthcare companies should I move to screening?"
- On **Analytics**: "Show me revenue trends by sector"
- On **Companies**: "Find logistics companies in Vilnius above 5M revenue"

### Session management

Each page has its own copilot chat history. Navigate away and come back — your previous conversation is still there. Pipeline copilot and Valuation copilot are separate sessions.

The Copilot routes your questions to the best specialist agent (deal triage, LBO modeler, value creation planner, etc.) using the same 24-agent routing system as the main chat.

---

## News Feed

The right pane shows live PE industry news from:

- **PE Hub** — deals, exits, personnel moves
- **Buyouts Insider** — US mid-market PE, fundraising, LP allocations
- **PE International** — global PE, LP/GP dynamics

Plus financial headlines from FT, Bloomberg, WSJ, Reuters, BBC, ERR, and Baltic Times. Refreshed every 30 minutes (configurable).

---

## Configuration

### Currency

Switch between **EUR** (default), **GBP**, and **USD**. All monetary figures across the app follow your preference.

### Language

11 languages supported: English, Estonian, Lithuanian, Latvian, Finnish, Swedish, Norwegian, Danish, French, German, Polish. The language selector is in the chat header — agents respond in your chosen language.

### Integrations

Baltic company registries (Estonia, Lithuania, Latvia) and web search (Tavily, EXA) status shown in the configuration panel.

---

## Data Coverage

| Country | Companies | Financial Rows | Source |
|---------|-----------|----------------|--------|
| Lithuania | 1,000 | 54,012 | rekvizitai.vz.lt |
| Estonia | 363 | 5,208 | ssb.ee |
| **Total** | **1,363** | **59,220** | |

Sectors: Healthcare, Software, Industrials, Financial Services, Business Services, Consumer.
