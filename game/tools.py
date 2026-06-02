"""Game state mutation tools — called by the LangGraph game master agent.

Each tool receives game state via closure and mutates it in place.
Tools return confirmation text that the agent weaves into its narrative.
"""

from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool

from game.engine import GameState, STAGES, LEVELS, CHARACTERS, calculate_score


_CAPITAL_CHANGE_MIN = -100_000
_CAPITAL_CHANGE_MAX = 200_000
_STAT_CHANGE_MIN = -3
_STAT_CHANGE_MAX = 3


def build_game_tools(state: GameState):
    """Build tools bound to a specific game state instance."""

    @tool
    def advance_stage() -> str:
        """Advance the game to the next stage. Call when the current stage's
        action is resolved and it's time to move on. Stages cycle through:
        Deal Sourcing → Analysis & Structuring → Due Diligence →
        Negotiation & Close → Value Creation. After Value Creation,
        a new round begins."""
        state.stage_idx += 1
        if state.stage_idx >= len(STAGES):
            state.stage_idx = 0
            state.round += 1
            state.special_power_used = False
            if state.round > state.total_rounds:
                state.game_over = True
                state.score = calculate_score(state)
                return (
                    f"GAME OVER! Final round complete. "
                    f"Score: {state.score:,}. "
                    f"Portfolio value: €{state.portfolio_value():,}. "
                    f"Deals closed: {state.deals_closed}, exited: {state.deals_exited}."
                )
            return (
                f"New round! Now in Round {state.round}/{state.total_rounds}, "
                f"Stage: {state.current_stage()}. "
                f"Special power is available again."
            )
        return (
            f"Advanced to {state.current_stage()} "
            f"(Round {state.round}/{state.total_rounds})."
        )

    @tool
    def adjust_resources(
        capital_change: int = 0,
        knowledge_change: int = 0,
        network_change: int = 0,
        reason: str = "",
    ) -> str:
        """Adjust the player's resources based on their action outcome.
        Use positive values for gains, negative for costs/losses.
        Always provide a reason explaining why resources changed.

        Guardrails: capital_change clamped to [-100000, +200000],
        knowledge/network clamped to [-3, +3] per call.
        Knowledge and network cannot drop below 0."""
        cap = max(_CAPITAL_CHANGE_MIN, min(_CAPITAL_CHANGE_MAX, capital_change))
        know = max(_STAT_CHANGE_MIN, min(_STAT_CHANGE_MAX, knowledge_change))
        net = max(_STAT_CHANGE_MIN, min(_STAT_CHANGE_MAX, network_change))

        state.capital += cap
        state.knowledge = max(0, state.knowledge + know)
        state.network = max(0, state.network + net)

        parts = []
        if cap > 0:
            parts.append(f"capital +€{cap:,}")
        elif cap < 0:
            parts.append(f"capital -€{abs(cap):,}")
        if know > 0:
            parts.append(f"knowledge +{know}")
        elif know < 0:
            parts.append(f"knowledge {know}")
        if net > 0:
            parts.append(f"network +{net}")
        elif net < 0:
            parts.append(f"network {net}")

        change_str = ", ".join(parts) if parts else "no change"
        return (
            f"Resources updated ({change_str}). "
            f"Reason: {reason}. "
            f"Current: €{state.capital:,} capital, "
            f"{state.knowledge} knowledge, {state.network} network."
        )

    @tool
    def close_deal(
        company_name: str,
        country: str,
        sector: str,
        entry_price: int,
        entry_multiple: float,
        revenue: int = 0,
        ebitda: int = 0,
    ) -> str:
        """Record a deal closing — the player has acquired a company.
        Deducts the entry price from capital and adds the company to the portfolio.
        Entry multiple should be realistic (4-8x EBITDA for Baltic mid-market)."""
        if entry_price > state.capital:
            return (
                f"Cannot close — entry price €{entry_price:,} exceeds "
                f"available capital €{state.capital:,}. "
                f"Negotiate a lower price or find co-investors."
            )
        state.capital -= entry_price
        company = {
            "name": company_name,
            "country": country,
            "sector": sector,
            "revenue": revenue,
            "ebitda": ebitda,
            "entry_multiple": entry_multiple,
            "current_multiple": entry_multiple,
            "entry_price": entry_price,
            "current_value": entry_price,
        }
        state.portfolio.append(company)
        state.deals_closed += 1
        return (
            f"Deal closed! Acquired {company_name} ({country}, {sector}) "
            f"at €{entry_price:,} ({entry_multiple}x EBITDA). "
            f"Portfolio now: {len(state.portfolio)} companies, "
            f"€{state.portfolio_value():,} total value. "
            f"Remaining capital: €{state.capital:,}."
        )

    @tool
    def exit_deal(
        company_name: str,
        exit_multiple: float,
        exit_reason: str = "trade sale",
    ) -> str:
        """Exit a portfolio company. Finds the company by name, calculates
        exit proceeds based on the exit multiple vs entry, and adds proceeds
        to capital. Exit multiple should be realistic (1.5-4x for good exits)."""
        target = None
        for i, co in enumerate(state.portfolio):
            name = co["name"] if isinstance(co, dict) else co.name
            if name.lower() == company_name.lower():
                target = (i, co)
                break
        if not target:
            return f"Company '{company_name}' not found in portfolio. Current portfolio: {[c['name'] if isinstance(c, dict) else c.name for c in state.portfolio]}"

        idx, co = target
        entry = co["entry_price"] if isinstance(co, dict) else co.entry_price
        proceeds = int(entry * exit_multiple)
        state.capital += proceeds
        state.portfolio.pop(idx)
        state.deals_exited += 1
        moic = round(exit_multiple, 1)
        return (
            f"Exited {company_name} via {exit_reason}! "
            f"Entry: €{entry:,} → Exit: €{proceeds:,} ({moic}x MOIC). "
            f"Capital now: €{state.capital:,}. "
            f"Portfolio: {len(state.portfolio)} companies remaining."
        )

    @tool
    def screen_deal(
        company_name: str,
        country: str,
        sector: str,
        revenue: int,
        ebitda: int,
        verdict: str = "promising",
    ) -> str:
        """Record that the player screened/evaluated a potential deal.
        Use when they're reviewing deal flow but haven't committed to acquiring.
        Verdict should be: promising, pass, needs-more-diligence."""
        state.deals_screened += 1
        return (
            f"Screened {company_name} ({country}, {sector}): "
            f"€{revenue:,} revenue, €{ebitda:,} EBITDA. "
            f"Verdict: {verdict}. "
            f"Total deals screened: {state.deals_screened}."
        )

    @tool
    def use_special_power() -> str:
        """Activate the character's special ability for this round.
        Each character has a unique power usable once per round.
        The power resets when a new round begins."""
        if state.special_power_used:
            return (
                "Special power already used this round! "
                "It will reset at the start of the next round."
            )
        char = CHARACTERS.get(state.character, {})
        state.special_power_used = True
        return (
            f"Special power activated: {char.get('ability', 'unknown')}. "
            f"This ability is now spent for Round {state.round}."
        )

    @tool
    def update_portfolio_value(
        company_name: str,
        new_multiple: float,
        reason: str = "",
    ) -> str:
        """Update a portfolio company's current valuation multiple.
        Use when value creation efforts, market conditions, or events
        change a company's worth. New multiple clamped to [1.0, 15.0]."""
        new_multiple = max(1.0, min(15.0, new_multiple))
        for co in state.portfolio:
            name = co["name"] if isinstance(co, dict) else co.name
            if name.lower() == company_name.lower():
                entry_m = co["entry_multiple"] if isinstance(co, dict) else co.entry_multiple
                entry_p = co["entry_price"] if isinstance(co, dict) else co.entry_price
                new_value = int(entry_p * (new_multiple / entry_m))
                if isinstance(co, dict):
                    co["current_multiple"] = new_multiple
                    co["current_value"] = new_value
                else:
                    co.current_multiple = new_multiple
                    co.current_value = new_value
                return (
                    f"{name} revalued: {entry_m}x → {new_multiple}x "
                    f"(€{new_value:,} current value). "
                    f"Reason: {reason}. "
                    f"Total portfolio: €{state.portfolio_value():,}."
                )
        return f"Company '{company_name}' not found in portfolio."

    @tool
    def get_game_status() -> str:
        """Get the current game status — resources, portfolio, round/stage info.
        Call this to check the player's current position before making decisions."""
        from game.engine import format_status
        return format_status(state)

    @tool
    def browse_pipeline(sector: str = "", min_revenue: int = 0, max_ev: int = 0) -> str:
        """Browse the deal pipeline for companies matching criteria.
        Returns up to 8 companies from the pipeline. Filter by sector
        (e.g. 'Healthcare', 'Software'), minimum revenue, or max enterprise value.
        These are REAL companies — use their exact names and financials."""
        matches = state.deal_pipeline
        if sector:
            matches = [c for c in matches if sector.lower() in c["sector"].lower()]
        if min_revenue:
            matches = [c for c in matches if c["revenue"] >= min_revenue]
        if max_ev and max_ev > 0:
            matches = [c for c in matches if c["ev"] <= max_ev]
        matches = matches[:8]
        if not matches:
            return "No companies match those criteria. Try broadening your search."
        lines = []
        for c in matches:
            margin = round(c["ebitda"] / max(1, c["revenue"]) * 100, 1)
            lines.append(
                f"• **{c['name']}** ({c['city']}, {c['country']})\n"
                f"  {c['sector']}{(' / ' + c['sub_sector']) if c['sub_sector'] else ''} | "
                f"€{c['revenue']/1e6:.1f}M rev | €{c['ebitda']/1e6:.1f}M EBITDA ({margin}% margin) | "
                f"EV €{c['ev']/1e6:.0f}M ({c['multiple']}x) | "
                f"{c['employees']} employees | {c['ownership']}\n"
                f"  {c['description']}"
            )
        return f"Pipeline ({len(matches)} matches):\n\n" + "\n\n".join(lines)

    return [
        advance_stage,
        adjust_resources,
        close_deal,
        exit_deal,
        screen_deal,
        use_special_power,
        update_portfolio_value,
        get_game_status,
        browse_pipeline,
    ]
