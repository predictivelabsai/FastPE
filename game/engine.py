"""PE Hero game engine — state management and game logic."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field

CHARACTERS = {
    "dealmaker": {
        "name": "Marcus Drake",
        "title": "The Dealmaker",
        "role": "Deal Sourcing & Origination",
        "icon": "\U0001f50d",
        "ability": "Open Door — bypass one gatekeeper per round to reach a company founder directly.",
        "start_capital": 50_000,
        "start_knowledge": 2,
        "start_network": 3,
        "description": (
            "A veteran dealmaker with an unmatched network across the Baltic PE ecosystem. "
            "You find opportunities others miss — but closing them is another story."
        ),
    },
    "analyst": {
        "name": "Elena Voss",
        "title": "The Analyst",
        "role": "Investment Analysis & Deal Execution",
        "icon": "\U0001f4ca",
        "ability": "Deep Model — build a forensic LBO model once per round that reveals hidden value or risk.",
        "start_capital": 30_000,
        "start_knowledge": 4,
        "start_network": 1,
        "description": (
            "A finance prodigy who sees the story behind the numbers. Your models are legendary, "
            "but sometimes the spreadsheet misses what a handshake reveals."
        ),
    },
    "investigator": {
        "name": "Raj Mehta",
        "title": "The Investigator",
        "role": "Due Diligence",
        "icon": "\U0001f575",
        "ability": "Red Flag — spot one critical risk per round that others miss, saving the fund from a bad deal.",
        "start_capital": 25_000,
        "start_knowledge": 5,
        "start_network": 1,
        "description": (
            "A forensic accountant turned PE diligence lead. Nothing escapes your review — "
            "you've killed more bad deals than most people have seen."
        ),
    },
    "operator": {
        "name": "Sofia Chen",
        "title": "The Operator",
        "role": "Portfolio Management & Value Creation",
        "icon": "\U0001f527",
        "ability": "Turnaround — implement one operational improvement per round that boosts portfolio company EBITDA.",
        "start_capital": 40_000,
        "start_knowledge": 3,
        "start_network": 2,
        "description": (
            "An operations expert who turns good companies into great ones. "
            "You've doubled margins at three portfolio companies and counting."
        ),
    },
    "fundraiser": {
        "name": "James Whitfield",
        "title": "The Fundraiser",
        "role": "Investor Relations & Fundraising",
        "icon": "\U0001f4bc",
        "ability": "LP Whisperer — once per round, secure a commitment from a hesitant LP.",
        "start_capital": 60_000,
        "start_knowledge": 1,
        "start_network": 4,
        "description": (
            "The LP whisperer. You've raised over €500M across three funds. "
            "Pensions, endowments, family offices — they all take your calls."
        ),
    },
}

LEVELS = {
    "associate": {
        "title": "Associate",
        "rounds": 5,
        "description": "Your first fund. Learn the ropes, source deals, build your track record.",
        "unlock": 0,
        "complexity": "Straightforward deals, cooperative LPs, stable markets.",
    },
    "vp": {
        "title": "Vice President",
        "rounds": 7,
        "description": "Lead deals end-to-end. Tougher negotiations, competitive auctions, board dynamics.",
        "unlock": 500,
        "complexity": "Competitive processes, hostile boards, covenant pressure.",
    },
    "partner": {
        "title": "Partner",
        "rounds": 10,
        "description": "Run the fund. Macro shocks, LP politics, exit timing, succession planning.",
        "unlock": 1200,
        "complexity": "Market crashes, LP defaults, regulatory shifts, cross-border complexity.",
    },
}

EVENT_CARDS = [
    {"name": "Baltic Tech Boom", "effect": "Software and SaaS valuations surge 25% across the Baltics.", "modifier": 1.25, "sectors": ["software"]},
    {"name": "ECB Rate Hike", "effect": "Debt financing costs jump. Leverage multiples compress.", "modifier": 0.85, "sectors": []},
    {"name": "Nordic PE Exit Wave", "effect": "Strategic buyers from Scandinavia flood the market. Exit multiples rise.", "modifier": 1.15, "sectors": []},
    {"name": "Supply Chain Disruption", "effect": "Industrial and logistics companies face margin pressure.", "modifier": 0.9, "sectors": ["industrials"]},
    {"name": "EU Green Deal Funding", "effect": "Cleantech and industrial efficiency plays attract subsidies.", "modifier": 1.2, "sectors": ["industrials"]},
    {"name": "Talent War", "effect": "Key management talent is being poached. Retention packages needed.", "modifier": 1.0, "sectors": []},
    {"name": "LP Co-Invest Appetite", "effect": "Several LPs want to co-invest. Capital available but governance gets complex.", "modifier": 1.1, "sectors": []},
    {"name": "Regulatory Tightening", "effect": "New Baltic AML regulations increase compliance costs across portfolio.", "modifier": 0.95, "sectors": []},
    {"name": "Add-on Opportunity", "effect": "A competitor to your portfolio company is available at 4x EBITDA.", "modifier": 1.0, "sectors": []},
    {"name": "Management Fraud Scandal", "effect": "A portfolio company CEO is caught inflating numbers. Crisis mode.", "modifier": 0.8, "sectors": []},
    {"name": "IPO Window Opens", "effect": "Nasdaq Baltic is hot. Several portfolio companies could list.", "modifier": 1.2, "sectors": []},
    {"name": "Currency Volatility", "effect": "EUR/USD swings impact export-heavy portfolio companies.", "modifier": 0.95, "sectors": []},
]

STAGES = ["Deal Sourcing", "Analysis & Structuring", "Due Diligence", "Negotiation & Close", "Value Creation"]


@dataclass
class PortfolioCompany:
    name: str
    country: str
    sector: str
    revenue: int
    ebitda: int
    entry_multiple: float
    current_multiple: float
    entry_price: int
    current_value: int


@dataclass
class GameState:
    character: str = ""
    character_name: str = ""
    player_name: str = "Player"
    level: str = "associate"
    round: int = 0
    stage_idx: int = 0
    capital: int = 0
    knowledge: int = 0
    network: int = 0
    portfolio: list = field(default_factory=list)
    deals_screened: int = 0
    deals_closed: int = 0
    deals_exited: int = 0
    fund_size: int = 0
    lp_commitments: int = 0
    special_power_used: bool = False
    events_history: list = field(default_factory=list)
    deal_pipeline: list = field(default_factory=list)
    total_rounds: int = 5
    game_over: bool = False
    score: int = 0

    def current_stage(self) -> str:
        if self.stage_idx < len(STAGES):
            return STAGES[self.stage_idx]
        return "End of Round"

    def portfolio_value(self) -> int:
        return sum(
            p.get("current_value", 0) if isinstance(p, dict) else p.current_value
            for p in self.portfolio
        )

    def to_dict(self) -> dict:
        return {
            "character": self.character,
            "character_name": self.character_name,
            "player_name": self.player_name,
            "level": self.level,
            "round": self.round,
            "stage_idx": self.stage_idx,
            "capital": self.capital,
            "knowledge": self.knowledge,
            "network": self.network,
            "portfolio": self.portfolio,
            "deals_screened": self.deals_screened,
            "deals_closed": self.deals_closed,
            "deals_exited": self.deals_exited,
            "fund_size": self.fund_size,
            "lp_commitments": self.lp_commitments,
            "special_power_used": self.special_power_used,
            "events_history": self.events_history,
            "deal_pipeline": self.deal_pipeline,
            "total_rounds": self.total_rounds,
            "game_over": self.game_over,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GameState":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def new_game(character_key: str, level: str = "associate", player_name: str = "Player") -> GameState:
    char = CHARACTERS[character_key]
    lvl = LEVELS[level]
    return GameState(
        character=character_key,
        character_name=char["name"],
        player_name=player_name,
        level=level,
        round=1,
        stage_idx=0,
        capital=char["start_capital"],
        knowledge=char["start_knowledge"],
        network=char["start_network"],
        total_rounds=lvl["rounds"],
        fund_size=200_000 if level == "associate" else 500_000 if level == "vp" else 1_000_000,
    )


def load_deal_pipeline(country: str = "LT", limit: int = 40) -> list[dict]:
    """Load real companies from the database for the game pipeline."""
    from db import fetch_all
    rows = fetch_all(
        "SELECT name, hq_city, country, sector, sub_sector, "
        "revenue_ltm, ebitda_ltm, enterprise_value, ask_multiple, "
        "employees, founded_year, ownership, description "
        "FROM pehero.companies WHERE country = %s "
        "AND revenue_ltm > 0 AND ebitda_ltm > 0 "
        "ORDER BY random() LIMIT %s",
        (country, limit),
    )
    return [
        {
            "name": r["name"],
            "city": r["hq_city"] or "",
            "country": r["country"] or country,
            "sector": (r["sector"] or "").replace("_", " ").title(),
            "sub_sector": (r["sub_sector"] or "").replace("_", " ").title(),
            "revenue": round(float(r["revenue_ltm"] or 0)),
            "ebitda": round(float(r["ebitda_ltm"] or 0)),
            "ev": round(float(r["enterprise_value"] or 0)),
            "multiple": round(float(r["ask_multiple"] or 0), 1),
            "employees": r["employees"] or 0,
            "founded": r["founded_year"] or 0,
            "ownership": (r["ownership"] or "").replace("_", " "),
            "description": (r["description"] or "")[:200],
        }
        for r in rows
    ]


def draw_event() -> dict:
    return random.choice(EVENT_CARDS)


def format_status(state: GameState) -> str:
    char = CHARACTERS.get(state.character, {})
    lvl = LEVELS.get(state.level, {})
    icon = char.get("icon", "")
    lines = [
        f"**Round {state.round}/{state.total_rounds}** | Stage: *{state.current_stage()}* | Level: {lvl.get('title', '')}",
        f"{icon} **{state.character_name}** — {char.get('title', '')} ({state.player_name})",
        f"€{state.capital:,} capital | {state.knowledge} knowledge | {state.network} network",
        f"Portfolio: {len(state.portfolio)} companies (€{state.portfolio_value():,} value)",
        f"Deals: {state.deals_screened} screened, {state.deals_closed} closed, {state.deals_exited} exited",
    ]
    if state.lp_commitments:
        lines.append(f"Fund: €{state.fund_size:,} target | €{state.lp_commitments:,} committed")
    if not state.special_power_used:
        lines.append(f"Special: *available* — {char.get('ability', '')}")
    else:
        lines.append("Special: *used this round*")
    return "\n".join(lines)


def calculate_score(state: GameState) -> int:
    return (
        state.portfolio_value()
        + state.capital
        + (state.knowledge * 500)
        + (state.network * 300)
        + (state.deals_closed * 1000)
        + (state.deals_exited * 2000)
    )
