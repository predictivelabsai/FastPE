"""Central registry of all 24 specialist PE agents.

Each `AgentSpec` is the source of truth for routing, UI rendering, and prompt
loading. The agent module (in agents/<category>/<slug>.py) owns its TOOLS +
build() but imports its SPEC from here to avoid drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentSpec:
    slug: str
    name: str
    category: str        # sourcing | underwriting | diligence | capital | portfolio
    icon: str            # unicode glyph for UI
    one_liner: str       # marketing sub-heading
    description: str     # full sentence for /agents page
    prefix: str          # router prefix (e.g., "triage:")
    example_prompts: tuple[str, ...] = field(default_factory=tuple)


CATEGORIES: list[dict] = [
    {
        "key": "sourcing",
        "name": "Deal Sourcing & Screening",
        "blurb": "Find proprietary deals before they hit the auction.",
        "icon": "◉",
    },
    {
        "key": "underwriting",
        "name": "LBO Underwriting Engine",
        "blurb": "Teaser to IC-ready LBO model in hours.",
        "icon": "◈",
    },
    {
        "key": "diligence",
        "name": "Due Diligence Stack",
        "blurb": "VDR audited, QoE validated, risks surfaced early.",
        "icon": "◆",
    },
    {
        "key": "capital",
        "name": "Capital & LP Relations",
        "blurb": "IC memos, teasers and LP updates your GP will sign.",
        "icon": "◐",
    },
    {
        "key": "asset_mgmt",
        "name": "Portfolio Operations",
        "blurb": "Drive EBITDA growth and value creation post-close.",
        "icon": "◼",
    },
]


AGENTS: tuple[AgentSpec, ...] = (
    # Deal Sourcing & Screening
    AgentSpec(
        slug="market_scanner", name="Market Scanner",
        category="sourcing", icon="⚯", prefix="scan:",
        one_liner="PitchBook + banker feeds + proprietary outreach, ranked by fit.",
        description="Continuously scans sell-side teasers, PitchBook/Grata/SourceScrub feeds, and proprietary founder outreach channels, deduplicating deals and surfacing those that fit your fund's mandate.",
        example_prompts=(
            "scan: lower-middle-market healthcare clinics, €5-15M EBITDA, Baltics",
            "What logistics deals surfaced this week in Lithuania?",
            "Any founder-owned veterinary clinics under €50M EV?",
            "Find Baltic real estate development companies €20-100M EV",
            "Show me insurance companies in Lithuania past 4-year hold",
        ),
    ),
    AgentSpec(
        slug="deal_triage", name="Deal Triage Agent",
        category="sourcing", icon="✓", prefix="triage:",
        one_liner="Go / no-go in 90 seconds against your fund mandate.",
        description="Screens a deal against your fund's investment criteria — check size, sector, geography, growth profile, leverage capacity — and returns a go/no-go with 3-bullet rationale.",
        example_prompts=(
            "triage: DR VET veterinary clinic, €3.8M revenue, 76 employees, Vilnius",
            "Should we pursue Baltic Transline? €397M revenue, logistics.",
            "Triage Kardiolita — is this a fit for our healthcare fund?",
            "Go/no-go on Eika Construction, €71M revenue, real estate development",
        ),
    ),
    AgentSpec(
        slug="comp_finder", name="Transaction Comps Finder",
        category="sourcing", icon="≡", prefix="comps:",
        one_liner="M&A + trading comps across 3 sources with outlier filtering.",
        description="Pulls precedent M&A transactions and public trading comps from PitchBook, MergerMarket, and Capital IQ, filters outliers, and returns a tight set for EV/EBITDA and EV/Revenue benchmarking.",
        example_prompts=(
            "comps: healthcare clinics precedent M&A 2022-2024, <€100M EV",
            "Find trading comps for a mid-market veterinary clinic chain",
            "What's the median EV/EBITDA for Baltic logistics deals?",
            "Benchmark EV/Revenue for insurance brokers in the Baltics",
        ),
    ),
    AgentSpec(
        slug="seller_intent", name="Owner Intent Signal",
        category="sourcing", icon="∿", prefix="intent:",
        one_liner="Ranks companies by likelihood of sale in the next 12 months.",
        description="Combines founder age, fund vintage, sponsor hold period, hiring freezes, and proxy-filing signals to score every target in your pipeline for likelihood of a sale process.",
        example_prompts=(
            "intent: founder-owned logistics companies, €50-150M revenue, Lithuania",
            "Which healthcare companies in our pipeline are most likely to sell?",
            "Rank founder-owned veterinary clinics by sale likelihood",
            "Show family-owned insurance brokers with highest succession risk",
        ),
    ),
    AgentSpec(
        slug="outreach_email", name="Outreach Email Drafter",
        category="sourcing", icon="✉", prefix="outreach:",
        one_liner="Personalized founder/broker outreach emails in your fund's voice.",
        description="Drafts cold outreach emails to founders, brokers, or intermediaries — personalized to the target's sector, size, and ownership situation, with a clear ask and your fund's positioning.",
        example_prompts=(
            "outreach: draft an intro email to the founder of DR VET",
            "Write a broker outreach email for healthcare clinic targets in Lithuania",
            "Draft a follow-up email to the Kardiolita management after our first call",
            "Write an outreach email to a placement agent for Fund V co-invest opportunities",
        ),
    ),
    AgentSpec(
        slug="loi_writer", name="LOI Writer",
        category="sourcing", icon="✍", prefix="loi:",
        one_liner="Non-binding letter of intent — price, structure, conditions, timeline.",
        description="Drafts a non-binding letter of intent covering indicative valuation, deal structure, key conditions, exclusivity period, timeline to close, and management rollover expectations.",
        example_prompts=(
            "loi: draft an LOI for Kardiolita at €85M EV",
            "Write a letter of intent for Northway — 10x LTM EBITDA, 60/40 equity-debt split",
            "Draft an IOI for the Baltic Transline logistics platform with an exclusivity ask",
            "Prepare an LOI with a 90-day exclusivity period and management rollover terms",
        ),
    ),

    # LBO Underwriting Engine
    AgentSpec(
        slug="rent_roll_parser", name="Cap Table Parser",
        category="underwriting", icon="☰", prefix="cap:",
        one_liner="Any cap table format → clean, fully-diluted ownership with waterfalls.",
        description="Parses cap tables in any format (Excel, PDF, Carta export) into a consistent schema with share classes, options, warrants, liquidation prefs, and fully-diluted ownership.",
        example_prompts=(
            "cap: parse the cap table for Kardiolita and show fully-diluted ownership",
            "Who has liquidation preference at DR VET?",
            "What's the options overhang at Northway?",
            "Show the top-5 holders and their capital invested for Eika Construction",
        ),
    ),
    AgentSpec(
        slug="t12_normalizer", name="LTM Financials Normalizer",
        category="underwriting", icon="∑", prefix="ltm:",
        one_liner="Messy owner financials → clean, add-back-adjusted LTM EBITDA.",
        description="Normalizes seller-provided financials onto a standard chart of accounts, applies QoE add-backs, separates one-time items, and flags revenue/EBITDA anomalies vs. industry benchmarks.",
        example_prompts=(
            "ltm: normalize the LTM P&L for DR VET with standard add-backs",
            "Compare Kardiolita EBITDA margin to healthcare peer median",
            "Show the add-back bridge from reported to adjusted EBITDA for Northway",
            "What's the revenue growth CAGR for DR VET over the last 24 months?",
        ),
    ),
    AgentSpec(
        slug="pro_forma_builder", name="LBO Model Builder",
        category="underwriting", icon="▤", prefix="lbo:",
        one_liner="5-year LBO model with sensitivity grid — editable assumptions.",
        description="Builds a full 5-year LBO model — revenue growth, margin expansion, capex, working capital, debt paydown, exit multiple. Sensitivity grid across the two most impactful variables.",
        example_prompts=(
            "lbo: build a 5-year model for Kardiolita at 12% rev growth, 300bps margin exp",
            "What's the base-case MOIC on Northway at 11x exit?",
            "Run a downside scenario: 5% growth, 100bps margin compression",
            "Show the sensitivity of IRR to entry vs exit multiple on DR VET",
        ),
    ),
    AgentSpec(
        slug="debt_stack_modeler", name="Debt Stack Modeler",
        category="underwriting", icon="▥", prefix="debt:",
        one_liner="Unitranche + mezz + revolver — with live leverage + DSCR.",
        description="Models LBO capital structures across senior / unitranche / mezzanine / seller notes / revolver — with total-leverage turns, DSCR, fixed-charge coverage, and refinance sensitivity.",
        example_prompts=(
            "debt: size a 5.5x unitranche on Kardiolita with a €5M revolver",
            "What's the max leverage at 1.35x FCCR on Northway?",
            "Add a 1.0x mezz tranche and re-solve for DSCR",
            "How sensitive is the stack to a 200bps rate increase?",
        ),
    ),
    AgentSpec(
        slug="return_metrics", name="Return Metrics",
        category="underwriting", icon="◈", prefix="ret:",
        one_liner="IRR, MOIC, levered/unlevered, with a value-creation bridge.",
        description="Computes return metrics from projected cash flows — levered/unlevered IRR, MOIC, equity multiple — and breaks results into multiple arbitrage, EBITDA growth, and debt paydown contributions.",
        example_prompts=(
            "ret: compute returns on the Kardiolita model",
            "Show the value-creation bridge for DR VET at 3x MOIC",
            "Decompose MOIC: EBITDA growth vs multiple arb vs debt paydown",
            "What's the unlevered IRR on Baltic Transline at the current base case?",
        ),
    ),

    # Due Diligence Stack
    AgentSpec(
        slug="doc_room_auditor", name="VDR Auditor",
        category="diligence", icon="☷", prefix="vdr:",
        one_liner="Cross-checks the data room against a full PE DD checklist.",
        description="Audits the seller's VDR against a 140-item PE diligence checklist, flagging missing documents, stale versions, and internal inconsistencies across legal, financial, commercial, and tech DD workstreams.",
        example_prompts=(
            "vdr: audit the data room for Kardiolita",
            "Which DD items are missing in the DR VET VDR?",
            "What's still outstanding on tax and legal for Northway?",
            "Compare VDR completeness across our top 3 active deals",
        ),
    ),
    AgentSpec(
        slug="lease_abstractor", name="Contract Abstractor",
        category="diligence", icon="▢", prefix="abstract:",
        one_liner="PDFs → contract abstracts with key terms, options, and risks.",
        description="Abstracts PDF contracts (customer MSAs, supplier agreements, employment contracts, IP licenses) into structured records — term, renewal, change-of-control triggers, exclusivity, termination rights — with page-cited references.",
        example_prompts=(
            "abstract: the top-10 customer contracts for Baltic Transline",
            "Any change-of-control triggers across Kardiolita's supplier contracts?",
            "List auto-renew + exclusivity clauses for Northway's top customers",
            "Which DR VET contracts expire in the next 12 months?",
        ),
    ),
    AgentSpec(
        slug="title_zoning", name="Legal & Regulatory Checker",
        category="diligence", icon="◰", prefix="legal:",
        one_liner="Corporate records + litigation + regulatory review, flags material issues.",
        description="Parses corporate minute books, litigation searches, and regulatory filings, flags material breaches, open litigation, licensure gaps, and change-of-control consents required at close.",
        example_prompts=(
            "legal: summarize legal issues for Kardiolita",
            "Are there any healthcare licensure gaps flagged on the Northway deal?",
            "Which change-of-control consents are required at DR VET close?",
            "Any open litigation above €1M exposure in the Eika Construction DD?",
        ),
    ),
    AgentSpec(
        slug="physical_condition", name="Operational Diligence Reviewer",
        category="diligence", icon="⌂", prefix="ops:",
        one_liner="Reads operational DD + QoE, builds a 100-day value-creation plan.",
        description="Reads operational reviews, quality-of-earnings reports, and process maps to extract working capital drag, systems gaps, and unit economics; outputs a 100-day post-close value creation plan.",
        example_prompts=(
            "ops: what operational gaps are flagged for DR VET?",
            "Build a 100-day plan for Kardiolita post-close",
            "Where is working capital tied up at Baltic Transline?",
            "What systems / ERP gaps need remediation post-close?",
        ),
    ),
    AgentSpec(
        slug="environmental_risk", name="ESG & Compliance Risk Flagger",
        category="diligence", icon="⚠", prefix="esg:",
        one_liner="ESG review — flags environmental, social, governance exposures.",
        description="Reads ESG disclosures, environmental site assessments, worker-safety records, and governance reports to identify ESG exposures, and recommends scope where further review is warranted (Phase II ESA, ethics review, etc).",
        example_prompts=(
            "esg: any environmental liabilities at the Baltic Transline logistics deal?",
            "Summarize ESG risk across my current pipeline",
            "What governance red flags were flagged for Kardiolita?",
            "Are there any diversity / turnover risks highlighted at Eika Construction?",
        ),
    ),

    # Capital & LP Relations
    AgentSpec(
        slug="investor_memo", name="IC Memo Writer",
        category="capital", icon="✎", prefix="memo:",
        one_liner="IC memo your investment committee will actually read.",
        description="Drafts a full investment-committee memo — exec summary, thesis, market, financials, value creation, risks, returns — from the deal's data in your system.",
        example_prompts=(
            "memo: draft the IC memo for Kardiolita",
            "Write a 5-page IC memo for DR VET",
            "Build the thesis + risks sections for Northway only",
            "Summarize the returns analysis for the IC pre-read",
        ),
    ),
    AgentSpec(
        slug="deal_teaser", name="Teaser Designer",
        category="capital", icon="✦", prefix="teaser:",
        one_liner="2-page teaser with thesis, financials, returns snapshot.",
        description="Generates a branded 2-page blind teaser suitable for co-investor or LP distribution — cover, company summary, key financials, returns table, thesis, risks.",
        example_prompts=(
            "teaser: build a co-invest teaser for Kardiolita",
            "Draft a blind LP teaser for the DR VET deal",
            "Create a 1-page executive summary for the Fund IV LPs",
            "Build a tombstone slide for the deal announcement",
        ),
    ),
    AgentSpec(
        slug="lp_update", name="LP Update Generator",
        category="capital", icon="⇄", prefix="lpupd:",
        one_liner="Quarterly LP letter with portfolio performance + outlook.",
        description="Generates a quarterly LP letter pulling fund-level IRR/MOIC/DPI, portfolio-company performance, deals closed/under contract, market outlook, and capital calls.",
        example_prompts=(
            "lpupd: draft Q1 letter for Fund IV LPs",
            "Generate a portfolio update for the Fund III LPs",
            "Write the market outlook section for the quarterly letter",
            "Summarize capital calls and distributions for this quarter",
        ),
    ),
    AgentSpec(
        slug="fundraising_crm", name="Fundraising CRM Copilot",
        category="capital", icon="◎", prefix="crm:",
        one_liner="LP pipeline ranked by fit, staleness, and commitment size.",
        description="Reads your LP CRM to rank prospects by mandate fit, staleness of last touch, and committed check size — and drafts the next outreach email or meeting prep doc.",
        example_prompts=(
            "crm: who are the top 10 LPs to reach out to for Fund V this week?",
            "Draft a re-engagement email to LPs we haven't touched in 60 days",
            "List endowment LPs that are a fit for our buyout mandate",
            "Draft a Fund V first-close announcement to qualified LPs",
        ),
    ),

    # Portfolio Operations
    AgentSpec(
        slug="rent_optimization", name="Pricing Optimization Agent",
        category="asset_mgmt", icon="↗", prefix="price:",
        one_liner="SKU/segment pricing recommendations from elasticity + peer benchmarks.",
        description="Evaluates in-place pricing vs. competitors, elasticity curves, and expiring contract base to recommend price increases at renewal and for new customers.",
        example_prompts=(
            "price: what pricing lift can we capture at Kardiolita at renewal?",
            "Where is pricing most below market across portcos?",
            "Rank DR VET customers by pricing headroom at renewal",
            "Model a 7% blended increase — estimate churn risk",
        ),
    ),
    AgentSpec(
        slug="opex_variance", name="EBITDA Variance Watcher",
        category="asset_mgmt", icon="Δ", prefix="ebitda:",
        one_liner="Monthly EBITDA variance vs. budget — with root-cause commentary.",
        description="Watches monthly actuals vs. budget across all portcos, surfaces variances above your threshold, and suggests root causes from GL-level expense breakouts.",
        example_prompts=(
            "ebitda: what's driving the EBITDA miss at DR VET this quarter?",
            "Show me the top 5 portco-wide EBITDA variances",
            "Which portcos are trending to miss budget this year?",
            "Break down the opex variance at Kardiolita by category",
        ),
    ),
    AgentSpec(
        slug="capex_prioritizer", name="Value Creation Prioritizer",
        category="asset_mgmt", icon="⚒", prefix="vc:",
        one_liner="Ranks value-creation initiatives by EBITDA impact and ROI.",
        description="Ranks pending value-creation initiatives across portfolio companies by expected EBITDA lift, return on invested capital, and urgency/risk.",
        example_prompts=(
            "vc: rank initiatives across the portfolio by EBITDA impact",
            "Should we prioritize pricing rollout or ERP replacement at Kardiolita?",
            "What's the highest-ROI initiative in DR VET's VCP?",
            "Show all 3-year VCP initiatives across the platform",
        ),
    ),
    AgentSpec(
        slug="tenant_churn", name="Customer Churn Predictor",
        category="asset_mgmt", icon="∠", prefix="churn:",
        one_liner="Scores each customer's renewal likelihood; drives retention actions.",
        description="Predicts each customer's renewal likelihood from contract economics, usage signals, support tickets, and tenure; prioritizes CS outreach to retain at-risk ARR.",
        example_prompts=(
            "churn: which DR VET customers are at highest renewal risk?",
            "Score renewal likelihood for Kardiolita's top 20 accounts",
            "What's the at-risk revenue across the portfolio for Q4 renewals?",
            "Draft a save play for Baltic Transline's top-3 at-risk accounts",
        ),
    ),
)


AGENTS_BY_SLUG: dict[str, AgentSpec] = {a.slug: a for a in AGENTS}
AGENTS_BY_CATEGORY: dict[str, list[AgentSpec]] = {}
for a in AGENTS:
    AGENTS_BY_CATEGORY.setdefault(a.category, []).append(a)


def all_agents() -> tuple[AgentSpec, ...]:
    return AGENTS


def by_slug(slug: str) -> AgentSpec | None:
    return AGENTS_BY_SLUG.get(slug)
