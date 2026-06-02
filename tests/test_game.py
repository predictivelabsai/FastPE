"""Comprehensive PE Hero game tests — engine logic + route flow.

Three full-game scenarios tested end-to-end:
  1. Marcus Drake (dealmaker) — select by name, play through all rounds
  2. Elena Voss (analyst) — select by number ("2"), play through rounds
  3. Raj Mehta (investigator) — select by number ("3"), test special ability + game over

Run with:  pytest -q tests/test_game.py         # no LLM
           pytest -q tests/test_game.py -v       # verbose
"""

from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import patch, MagicMock

import pytest

from game.engine import (
    CHARACTERS, LEVELS, STAGES, EVENT_CARDS,
    GameState, new_game, draw_event, format_status, calculate_score,
    PortfolioCompany,
)
from game.prompts import GAME_MASTER_SYSTEM, WELCOME, CHARACTER_SELECT_ROW, GAME_OVER
from game.routes import CHAR_MAP, _welcome_text, _game_over_text


# ───────────────────────────────── Engine unit tests ─────────────────────────

class TestCharacters:
    def test_all_five_characters_defined(self):
        assert len(CHARACTERS) == 5
        assert set(CHARACTERS.keys()) == {"dealmaker", "analyst", "investigator", "operator", "fundraiser"}

    @pytest.mark.parametrize("key", CHARACTERS.keys())
    def test_character_has_required_fields(self, key):
        c = CHARACTERS[key]
        for field in ("name", "title", "role", "icon", "ability",
                      "start_capital", "start_knowledge", "start_network", "description"):
            assert field in c, f"{key} missing {field}"

    def test_starting_stats_are_positive(self):
        for key, c in CHARACTERS.items():
            assert c["start_capital"] > 0, f"{key} capital <= 0"
            assert c["start_knowledge"] >= 1, f"{key} knowledge < 1"
            assert c["start_network"] >= 1, f"{key} network < 1"


class TestLevels:
    def test_three_levels_defined(self):
        assert len(LEVELS) == 3
        assert list(LEVELS.keys()) == ["associate", "vp", "partner"]

    def test_levels_have_increasing_rounds(self):
        rounds = [LEVELS[k]["rounds"] for k in LEVELS]
        assert rounds == sorted(rounds)

    def test_levels_have_increasing_unlock_scores(self):
        unlocks = [LEVELS[k]["unlock"] for k in LEVELS]
        assert unlocks == sorted(unlocks)
        assert unlocks[0] == 0


class TestStages:
    def test_five_stages(self):
        assert len(STAGES) == 5
        assert STAGES[0] == "Deal Sourcing"
        assert STAGES[-1] == "Value Creation"


class TestEventCards:
    def test_events_have_required_fields(self):
        for e in EVENT_CARDS:
            assert "name" in e
            assert "effect" in e
            assert "modifier" in e
            assert isinstance(e["modifier"], (int, float))

    def test_draw_event_returns_valid(self):
        for _ in range(20):
            e = draw_event()
            assert e in EVENT_CARDS


class TestGameState:
    def test_new_game_defaults(self):
        state = new_game("dealmaker")
        assert state.character == "dealmaker"
        assert state.character_name == "Marcus Drake"
        assert state.round == 1
        assert state.stage_idx == 0
        assert state.capital == 50_000
        assert state.knowledge == 2
        assert state.network == 3
        assert state.total_rounds == 5
        assert not state.game_over
        assert state.score == 0

    def test_new_game_vp_level(self):
        state = new_game("analyst", level="vp")
        assert state.level == "vp"
        assert state.total_rounds == 7
        assert state.fund_size == 500_000

    def test_new_game_partner_level(self):
        state = new_game("operator", level="partner")
        assert state.level == "partner"
        assert state.total_rounds == 10
        assert state.fund_size == 1_000_000

    def test_current_stage(self):
        state = new_game("dealmaker")
        assert state.current_stage() == "Deal Sourcing"
        state.stage_idx = 2
        assert state.current_stage() == "Due Diligence"
        state.stage_idx = 99
        assert state.current_stage() == "End of Round"

    def test_portfolio_value_empty(self):
        state = new_game("dealmaker")
        assert state.portfolio_value() == 0

    def test_portfolio_value_with_companies(self):
        state = new_game("dealmaker")
        state.portfolio = [
            {"name": "Co A", "current_value": 100_000},
            {"name": "Co B", "current_value": 250_000},
        ]
        assert state.portfolio_value() == 350_000

    def test_serialization_round_trip(self):
        state = new_game("investigator", player_name="TestPlayer")
        state.deals_closed = 3
        state.knowledge = 7
        state.events_history = ["Baltic Tech Boom"]
        d = state.to_dict()
        restored = GameState.from_dict(d)
        assert restored.character == "investigator"
        assert restored.deals_closed == 3
        assert restored.knowledge == 7
        assert restored.events_history == ["Baltic Tech Boom"]

    def test_serialization_json_round_trip(self):
        state = new_game("fundraiser")
        state.capital = 42_000
        s = json.dumps(state.to_dict())
        restored = GameState.from_dict(json.loads(s))
        assert restored.capital == 42_000
        assert restored.character_name == "James Whitfield"


class TestScoring:
    def test_score_zero_start(self):
        state = new_game("dealmaker")
        score = calculate_score(state)
        expected = 50_000 + (2 * 500) + (3 * 300)
        assert score == expected

    def test_score_with_deals(self):
        state = new_game("analyst")
        state.deals_closed = 2
        state.deals_exited = 1
        state.portfolio = [{"name": "X", "current_value": 200_000}]
        score = calculate_score(state)
        expected = (200_000 + 30_000 + (4 * 500) + (1 * 300)
                    + (2 * 1000) + (1 * 2000))
        assert score == expected

    def test_score_increases_with_activity(self):
        state = new_game("operator")
        base = calculate_score(state)
        state.deals_closed += 1
        assert calculate_score(state) > base
        state.knowledge += 1
        assert calculate_score(state) > base + 1000


class TestFormatStatus:
    def test_format_includes_character(self):
        state = new_game("dealmaker")
        status = format_status(state)
        assert "Marcus Drake" in status
        assert "Round 1/5" in status
        assert "Deal Sourcing" in status

    def test_format_shows_special_available(self):
        state = new_game("analyst")
        status = format_status(state)
        assert "available" in status
        assert "Deep Model" in status

    def test_format_shows_special_used(self):
        state = new_game("analyst")
        state.special_power_used = True
        status = format_status(state)
        assert "used this round" in status


# ───────────────────────────────── CHAR_MAP tests ────────────────────────────

class TestCharMap:
    @pytest.mark.parametrize("input_val,expected", [
        ("1", "dealmaker"), ("2", "analyst"), ("3", "investigator"),
        ("4", "operator"), ("5", "fundraiser"),
    ])
    def test_numeric_selection(self, input_val, expected):
        assert CHAR_MAP[input_val] == expected

    @pytest.mark.parametrize("input_val,expected", [
        ("marcus drake", "dealmaker"),
        ("elena voss", "analyst"),
        ("raj mehta", "investigator"),
        ("sofia chen", "operator"),
        ("james whitfield", "fundraiser"),
    ])
    def test_full_name_selection(self, input_val, expected):
        assert CHAR_MAP[input_val] == expected

    @pytest.mark.parametrize("input_val,expected", [
        ("marcus", "dealmaker"),
        ("elena", "analyst"),
        ("raj", "investigator"),
        ("sofia", "operator"),
        ("james", "fundraiser"),
    ])
    def test_first_name_selection(self, input_val, expected):
        assert CHAR_MAP[input_val] == expected

    @pytest.mark.parametrize("input_val,expected", [
        ("dealmaker", "dealmaker"),
        ("analyst", "analyst"),
        ("investigator", "investigator"),
        ("operator", "operator"),
        ("fundraiser", "fundraiser"),
    ])
    def test_key_selection(self, input_val, expected):
        assert CHAR_MAP[input_val] == expected


# ───────────────────────────────── Prompt / text tests ───────────────────────

class TestWelcomeText:
    def test_welcome_includes_all_characters(self):
        text = _welcome_text()
        for char in CHARACTERS.values():
            assert char["name"] in text

    def test_welcome_includes_table_header(self):
        text = _welcome_text()
        assert "| Name |" in text or "Name" in text

    def test_welcome_includes_instruction(self):
        text = _welcome_text()
        assert "Type a character name or number (1-5)" in text


class TestGameOverText:
    def test_game_over_includes_scorecard(self):
        state = new_game("dealmaker")
        state.game_over = True
        state.deals_closed = 2
        state.deals_exited = 1
        text = _game_over_text(state)
        assert "Scorecard" in text
        assert "Marcus Drake" in text
        assert "TOTAL SCORE" in text

    def test_game_over_low_score_tone(self):
        state = new_game("analyst")
        state.game_over = True
        state.capital = 0
        state.knowledge = 0
        state.network = 0
        text = _game_over_text(state)
        assert "Tough round" in text or "Not bad" in text or "Solid" in text

    def test_game_over_high_score_unlock(self):
        state = new_game("fundraiser")
        state.game_over = True
        state.deals_closed = 5
        state.deals_exited = 3
        state.capital = 200_000
        state.knowledge = 10
        state.network = 10
        state.portfolio = [{"name": "X", "current_value": 500_000}]
        text = _game_over_text(state)
        assert "LEVEL UNLOCKED" in text or "unlock" in text.lower()


# ───────────────────────────────── Route-level flow tests ────────────────────

class _FakeRequest:
    """Minimal request mock for route handlers."""
    def __init__(self, session: dict | None = None):
        self.session = session if session is not None else {}
        self._form_data = {}

    async def form(self):
        return self._form_data


def _parse_sse_events(raw: str) -> list[tuple[str, dict]]:
    """Parse raw SSE text into (event_name, data) tuples."""
    events = []
    lines = raw.split("\n")
    current_event = ""
    for line in lines:
        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                events.append((current_event, data))
            except json.JSONDecodeError:
                pass
    return events


def _collect_tokens(events: list[tuple[str, dict]]) -> str:
    """Extract all token text from SSE events."""
    return "".join(d.get("text", "") for name, d in events if name == "token")


def _make_fake_agent(response_text: str, tool_calls: list[dict] | None = None):
    """Build a fake LangGraph agent that yields astream_events.

    tool_calls: list of {"name": "tool_name", "args": {...}} dicts.
    Each tool is yielded as on_tool_start + on_tool_end, then the response
    text is streamed as on_chat_model_stream chunks.
    """

    class FakeChunk:
        def __init__(self, text, is_tool_call=False):
            self.content = text
            self.tool_call_chunks = [{}] if is_tool_call else None

    class FakeGraph:
        def __init__(self, state):
            self._state = state

        async def astream_events(self, inputs, version="v2"):
            # Yield tool calls first (the agent reasons then acts)
            for tc in (tool_calls or []):
                yield {
                    "event": "on_tool_start",
                    "name": tc["name"],
                    "data": {"input": tc.get("args", {})},
                }
                # Actually invoke the tool on the real state
                from game.tools import build_game_tools
                tools = build_game_tools(self._state)
                tool_map = {t.name: t for t in tools}
                tool_fn = tool_map.get(tc["name"])
                if tool_fn:
                    result = tool_fn.invoke(tc.get("args", {}))
                else:
                    result = f"unknown tool: {tc['name']}"
                yield {
                    "event": "on_tool_end",
                    "name": tc["name"],
                    "data": {"output": result},
                }

            # Stream response text
            words = response_text.split(" ")
            for i in range(0, len(words), 3):
                chunk_text = " ".join(words[i:i+3]) + " "
                yield {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": FakeChunk(chunk_text)},
                }

    return FakeGraph


async def _run_training_chat(
    session: dict,
    msg: str,
    llm_response: str = "Test response. 1. **Option A** 2. **Option B** 3. **Option C**",
    tool_calls: list[dict] | None = None,
):
    """Invoke training_chat and collect all SSE events.

    Mocks the LangGraph game agent to avoid LLM calls. If tool_calls are
    provided, they're executed against the real game state before the
    response text is streamed.
    """
    from game.routes import register_game_routes

    captured_handler = {}

    def fake_rt(path, methods=None):
        def decorator(fn):
            captured_handler[path] = fn
            return fn
        return decorator

    register_game_routes(fake_rt)
    handler = captured_handler.get("/app/training/chat")
    assert handler, "training_chat route not registered"

    req = _FakeRequest(session)
    req._form_data = {"msg": msg}

    FakeGraphClass = _make_fake_agent(llm_response, tool_calls)

    def fake_build_game_agent(state, system_prompt):
        return FakeGraphClass(state)

    with patch("game.agent.build_game_agent", side_effect=fake_build_game_agent):
        response = await handler(req)

        raw = b""
        if hasattr(response, "body_iterator"):
            async for chunk in response.body_iterator:
                if isinstance(chunk, str):
                    raw += chunk.encode()
                else:
                    raw += chunk
        elif hasattr(response, "body"):
            raw = response.body if isinstance(response.body, bytes) else response.body.encode()

    return _parse_sse_events(raw.decode()), session


# ───────────────────────────────── Scenario 1: Marcus Drake (by name) ────────

class TestScenario1MarcusDrake:
    """Full flow: select Marcus Drake by full name, play 5 rounds."""

    @pytest.mark.asyncio
    async def test_01_invalid_input_shows_welcome(self):
        events, sess = await _run_training_chat({}, "hello world")
        text = _collect_tokens(events)
        assert "Choose your character" in text or "PE Hero Training" in text
        assert "pe_hero_state" not in sess

    @pytest.mark.asyncio
    async def test_02_select_marcus_drake_by_name(self):
        events, sess = await _run_training_chat(
            {}, "Marcus Drake",
            llm_response="Welcome to the fund! Here are 3 deals:\n1. **Pursue** NordTech\n2. **Deep-dive** into pipeline\n3. **Network** at summit"
        )
        text = _collect_tokens(events)
        assert "Marcus Drake" in text
        assert "The Dealmaker" in text
        assert "€50,000" in text or "50,000" in text

        assert "pe_hero_state" in sess
        state = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert state.character == "dealmaker"
        assert state.round == 1
        assert state.capital == 50_000

    @pytest.mark.asyncio
    async def test_03_play_round_advances_state(self):
        state = new_game("dealmaker")
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(
            sess, "1",
            llm_response="Great move! 1. **Build** model 2. **Review** data 3. **Call** management",
            tool_calls=[
                {"name": "adjust_resources", "args": {"knowledge_change": 1, "reason": "good analysis"}},
                {"name": "advance_stage", "args": {}},
            ],
        )
        text = _collect_tokens(events)
        assert len(text) > 0

        updated = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert updated.stage_idx == 1

    @pytest.mark.asyncio
    async def test_04_deal_closed_increments(self):
        state = new_game("dealmaker")
        state.stage_idx = 3
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(
            sess, "Close the deal",
            llm_response="BOOM! 1. **Optimize** ops 2. **Hire** CFO 3. **Expand** to Latvia",
            tool_calls=[
                {"name": "close_deal", "args": {
                    "company_name": "NordTech", "country": "Estonia",
                    "sector": "software", "entry_price": 10_000,
                    "entry_multiple": 6.0, "revenue": 5_000_000, "ebitda": 1_000_000,
                }},
            ],
        )
        updated = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert updated.deals_closed >= 1
        assert len(updated.portfolio) == 1
        assert updated.capital == 40_000

    @pytest.mark.asyncio
    async def test_05_special_power_usage(self):
        state = new_game("dealmaker")
        assert not state.special_power_used
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(
            sess, "Use my special ability to bypass the gatekeeper",
            llm_response="Open Door activated! 1. **Pitch** 2. **Negotiate** 3. **Walk**",
            tool_calls=[{"name": "use_special_power", "args": {}}],
        )
        updated = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert updated.special_power_used

    @pytest.mark.asyncio
    async def test_06_round_advancement(self):
        state = new_game("dealmaker")
        state.stage_idx = 4
        state.round = 1
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(
            sess, "Complete value creation phase",
            llm_response="Next round! 1. **Scan** 2. **Follow-up** 3. **Network**",
            tool_calls=[{"name": "advance_stage", "args": {}}],
        )
        updated = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert updated.round == 2
        assert updated.stage_idx == 0
        assert not updated.special_power_used

    @pytest.mark.asyncio
    async def test_07_game_over_triggers(self):
        state = new_game("dealmaker")
        state.stage_idx = 4
        state.round = 5
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(
            sess, "Final move",
            llm_response="What a run! 1. **Review** 2. **Celebrate** 3. **Replay**",
            tool_calls=[{"name": "advance_stage", "args": {}}],
        )
        updated = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert updated.game_over
        assert updated.score > 0
        text = _collect_tokens(events)
        assert "FINAL WHISTLE" in text or "Scorecard" in text

    @pytest.mark.asyncio
    async def test_08_reset_clears_state(self):
        state = new_game("dealmaker")
        state.round = 3
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(sess, "reset")
        text = _collect_tokens(events)
        assert "Game reset" in text
        assert "pe_hero_state" not in sess


# ───────────────────────────────── Scenario 2: Elena Voss (by number) ────────

class TestScenario2ElenaVoss:
    """Select by number "2", analyst flow with knowledge gains."""

    @pytest.mark.asyncio
    async def test_01_select_by_number(self):
        events, sess = await _run_training_chat(
            {}, "2",
            llm_response="Welcome analyst! Time to crunch numbers. 1. **Analyze** 2. **Model** 3. **Research**"
        )
        text = _collect_tokens(events)
        assert "Elena Voss" in text
        assert "The Analyst" in text
        state = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert state.character == "analyst"
        assert state.knowledge == 4

    @pytest.mark.asyncio
    async def test_02_knowledge_gain(self):
        state = new_game("analyst")
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(
            sess, "Deep-dive the financials",
            llm_response="Excellent analysis! 1. **Flag** 2. **Ignore** 3. **Investigate**",
            tool_calls=[
                {"name": "adjust_resources", "args": {"knowledge_change": 1, "reason": "deep financial analysis"}},
            ],
        )
        updated = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert updated.knowledge == 5

    @pytest.mark.asyncio
    async def test_03_network_gain(self):
        state = new_game("analyst")
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(
            sess, "Attend Baltic PE conference",
            llm_response="Great networking! 1. **Follow-up** 2. **Pitch** 3. **Schedule**",
            tool_calls=[
                {"name": "adjust_resources", "args": {"network_change": 1, "reason": "conference networking"}},
            ],
        )
        updated = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert updated.network == 2

    @pytest.mark.asyncio
    async def test_04_multiple_stages_in_sequence(self):
        state = new_game("analyst")
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        for i in range(4):
            events, sess = await _run_training_chat(
                sess, f"Action {i+1}",
                llm_response="Moving on! 1. **A** 2. **B** 3. **C**",
                tool_calls=[{"name": "advance_stage", "args": {}}],
            )

        updated = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert updated.stage_idx == 4

    @pytest.mark.asyncio
    async def test_05_exit_increments(self):
        state = new_game("analyst")
        state.deals_closed = 1
        state.portfolio = [
            {"name": "TestCo", "country": "Latvia", "sector": "software",
             "revenue": 5_000_000, "ebitda": 1_000_000,
             "entry_multiple": 6.0, "current_multiple": 6.0,
             "entry_price": 6_000_000, "current_value": 6_000_000},
        ]
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(
            sess, "Exit TestCo via trade sale",
            llm_response="Great exit! 1. **Reinvest** 2. **Distribute** 3. **Hold**",
            tool_calls=[
                {"name": "exit_deal", "args": {"company_name": "TestCo", "exit_multiple": 2.5, "exit_reason": "trade sale"}},
            ],
        )
        updated = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert updated.deals_exited >= 1
        assert len(updated.portfolio) == 0

    @pytest.mark.asyncio
    async def test_06_game_over_after_all_rounds(self):
        state = new_game("analyst")
        state.round = 5
        state.stage_idx = 4
        state.deals_closed = 2
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(
            sess, "Final analysis",
            llm_response="The fund term ends! 1. **Review** 2. **Next** 3. **Done**",
            tool_calls=[{"name": "advance_stage", "args": {}}],
        )
        updated = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert updated.game_over
        text = _collect_tokens(events)
        assert "Scorecard" in text or "FINAL WHISTLE" in text

    @pytest.mark.asyncio
    async def test_07_game_over_replay_resets(self):
        state = new_game("analyst")
        state.game_over = True
        state.score = 500
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(sess, "replay")
        text = _collect_tokens(events)
        assert "PE Hero Training" in text or "Choose your character" in text
        assert "pe_hero_state" not in sess


# ───────────────────────────────── Scenario 3: Raj Mehta (by number) ─────────

class TestScenario3RajMehta:
    """Select by number "3", investigator flow with ability + level up."""

    @pytest.mark.asyncio
    async def test_01_select_by_number_3(self):
        events, sess = await _run_training_chat(
            {}, "3",
            llm_response="Welcome investigator! 1. **Scan** 2. **Review** 3. **Network**"
        )
        text = _collect_tokens(events)
        assert "Raj Mehta" in text
        assert "The Investigator" in text
        state = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert state.character == "investigator"
        assert state.knowledge == 5
        assert state.network == 1

    @pytest.mark.asyncio
    async def test_02_select_by_first_name(self):
        events, sess = await _run_training_chat(
            {}, "raj",
            llm_response="Let's go! 1. **A** 2. **B** 3. **C**"
        )
        state = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert state.character == "investigator"

    @pytest.mark.asyncio
    async def test_03_red_flag_ability(self):
        state = new_game("investigator")
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(
            sess, "Use my Red Flag ability to spot risks",
            llm_response="Critical risk spotted! 1. **Walk** 2. **Renegotiate** 3. **Proceed**",
            tool_calls=[{"name": "use_special_power", "args": {}}],
        )
        updated = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert updated.special_power_used

    @pytest.mark.asyncio
    async def test_04_special_cant_use_twice(self):
        state = new_game("investigator")
        state.special_power_used = True
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(
            sess, "Use my special power again",
            llm_response="Already used! 1. **A** 2. **B** 3. **C**",
            tool_calls=[{"name": "use_special_power", "args": {}}],
        )
        updated = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert updated.special_power_used

    @pytest.mark.asyncio
    async def test_05_new_round_resets_special(self):
        state = new_game("investigator")
        state.special_power_used = True
        state.stage_idx = 4
        state.round = 1
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(
            sess, "Advance",
            llm_response="Next round! 1. **A** 2. **B** 3. **C**",
            tool_calls=[{"name": "advance_stage", "args": {}}],
        )
        updated = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert updated.round == 2
        assert not updated.special_power_used

    @pytest.mark.asyncio
    async def test_06_complete_game_and_score(self):
        state = new_game("investigator")
        state.round = 5
        state.stage_idx = 4
        state.deals_closed = 3
        state.deals_exited = 2
        state.knowledge = 8
        state.capital = 100_000
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(
            sess, "Final move",
            llm_response="Game over! 1. **Done** 2. **Review** 3. **Next**",
            tool_calls=[{"name": "advance_stage", "args": {}}],
        )
        updated = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert updated.game_over
        assert updated.score > 0
        expected_min = 100_000 + (8 * 500) + (1 * 300) + (3 * 1000) + (2 * 2000)
        assert updated.score >= expected_min

    @pytest.mark.asyncio
    async def test_07_level_up_when_qualified(self):
        state = new_game("investigator")
        state.game_over = True
        state.score = 600
        sess = {
            "pe_hero_state": json.dumps(state.to_dict()),
            "pe_hero_level": "associate",
        }

        events, sess = await _run_training_chat(sess, "level up")
        text = _collect_tokens(events)
        assert "LEVEL UP" in text
        assert "Vice President" in text
        assert sess.get("pe_hero_level") == "vp"
        assert "pe_hero_state" not in sess

    @pytest.mark.asyncio
    async def test_08_level_up_denied_when_score_too_low(self):
        state = new_game("investigator")
        state.game_over = True
        state.score = 100
        sess = {
            "pe_hero_state": json.dumps(state.to_dict()),
            "pe_hero_level": "associate",
        }

        events, sess = await _run_training_chat(sess, "level up")
        text = _collect_tokens(events)
        assert "haven't unlocked" in text

    @pytest.mark.asyncio
    async def test_09_new_game_command(self):
        state = new_game("investigator")
        state.round = 3
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(sess, "new game")
        text = _collect_tokens(events)
        assert "Game reset" in text
        assert "pe_hero_state" not in sess


# ───────────────────────────────── SSE event structure tests ─────────────────

class TestSSEEvents:
    @pytest.mark.asyncio
    async def test_session_event_emitted(self):
        events, _ = await _run_training_chat({}, "invalid")
        session_events = [(n, d) for n, d in events if n == "session"]
        assert len(session_events) >= 1
        assert session_events[0][1]["sid"] == "training"

    @pytest.mark.asyncio
    async def test_agent_route_event_emitted(self):
        events, _ = await _run_training_chat({}, "invalid")
        route_events = [(n, d) for n, d in events if n == "agent_route"]
        assert len(route_events) >= 1
        assert route_events[0][1]["slug"] == "pe_hero_game"
        assert route_events[0][1]["agent"] == "Coach V"

    @pytest.mark.asyncio
    async def test_done_event_emitted(self):
        events, _ = await _run_training_chat({}, "invalid")
        done_events = [(n, d) for n, d in events if n == "done"]
        assert len(done_events) >= 1

    @pytest.mark.asyncio
    async def test_tool_events_on_character_select(self):
        events, _ = await _run_training_chat(
            {}, "1",
            llm_response="Welcome! 1. **A** 2. **B** 3. **C**"
        )
        token_events = [(n, d) for n, d in events if n == "token"]
        assert len(token_events) > 0

    @pytest.mark.asyncio
    async def test_tool_events_on_game_turn(self):
        state = new_game("dealmaker")
        sess = {"pe_hero_state": json.dumps(state.to_dict())}
        events, _ = await _run_training_chat(
            sess, "Do something",
            llm_response="Nice! 1. **A** 2. **B** 3. **C**",
            tool_calls=[{"name": "adjust_resources", "args": {"knowledge_change": 1, "reason": "test"}}],
        )
        event_names = [n for n, _ in events]
        assert "tool_start" in event_names
        assert "tool_end" in event_names
        tool_start_idx = event_names.index("tool_start")
        tool_end_idx = event_names.index("tool_end")
        assert tool_start_idx < tool_end_idx


# ───────────────────────────────── Edge cases ────────────────────────────────

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_message_not_accepted(self):
        from game.routes import register_game_routes
        captured = {}
        def fake_rt(path, methods=None):
            def decorator(fn):
                captured[path] = fn
                return fn
            return decorator
        register_game_routes(fake_rt)
        handler = captured["/app/training/chat"]

        req = _FakeRequest({})
        req._form_data = {"msg": ""}
        response = await handler(req)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_whitespace_only_message(self):
        from game.routes import register_game_routes
        captured = {}
        def fake_rt(path, methods=None):
            def decorator(fn):
                captured[path] = fn
                return fn
            return decorator
        register_game_routes(fake_rt)
        handler = captured["/app/training/chat"]

        req = _FakeRequest({})
        req._form_data = {"msg": "   "}
        response = await handler(req)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_game_over_state_shows_score(self):
        state = new_game("operator")
        state.game_over = True
        state.deals_closed = 1
        state.score = 500
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, _ = await _run_training_chat(sess, "what now?")
        text = _collect_tokens(events)
        assert "TOTAL SCORE" in text or "Scorecard" in text

    @pytest.mark.asyncio
    async def test_corrupt_session_treated_as_no_state(self):
        sess = {"pe_hero_state": "not valid json at all"}
        events, _ = await _run_training_chat(sess, "hello")
        text = _collect_tokens(events)
        assert "PE Hero Training" in text or "Choose your character" in text

    @pytest.mark.asyncio
    async def test_all_five_characters_selectable(self):
        for i, (key, char) in enumerate(CHARACTERS.items(), 1):
            events, sess = await _run_training_chat(
                {}, str(i),
                llm_response="Go! 1. **A** 2. **B** 3. **C**"
            )
            state = GameState.from_dict(json.loads(sess["pe_hero_state"]))
            assert state.character == key, f"Number {i} should map to {key}"
            assert state.character_name == char["name"]


# ───────────────────────────────── Tool unit tests ───────────────────────────

class TestGameTools:
    """Test game tools directly — they mutate GameState via closure."""

    def _tools(self, state):
        from game.tools import build_game_tools
        tools = build_game_tools(state)
        return {t.name: t for t in tools}

    def test_advance_stage_increments(self):
        state = new_game("dealmaker")
        tools = self._tools(state)
        result = tools["advance_stage"].invoke({})
        assert state.stage_idx == 1
        assert "Analysis & Structuring" in result

    def test_advance_stage_wraps_round(self):
        state = new_game("dealmaker")
        state.stage_idx = 4
        state.special_power_used = True
        tools = self._tools(state)
        result = tools["advance_stage"].invoke({})
        assert state.round == 2
        assert state.stage_idx == 0
        assert not state.special_power_used
        assert "New round" in result

    def test_advance_stage_triggers_game_over(self):
        state = new_game("dealmaker")
        state.stage_idx = 4
        state.round = 5
        tools = self._tools(state)
        result = tools["advance_stage"].invoke({})
        assert state.game_over
        assert state.score > 0
        assert "GAME OVER" in result

    def test_adjust_resources_positive(self):
        state = new_game("analyst")
        tools = self._tools(state)
        tools["adjust_resources"].invoke({
            "capital_change": 5000,
            "knowledge_change": 2,
            "network_change": 1,
            "reason": "good analysis",
        })
        assert state.capital == 35_000
        assert state.knowledge == 6
        assert state.network == 2

    def test_adjust_resources_clamped(self):
        state = new_game("dealmaker")
        tools = self._tools(state)
        tools["adjust_resources"].invoke({
            "capital_change": 999_999,
            "knowledge_change": 10,
            "reason": "overflow test",
        })
        assert state.capital == 250_000
        assert state.knowledge == 5

    def test_adjust_resources_negative_floor(self):
        state = new_game("analyst")  # starts with knowledge=4
        tools = self._tools(state)
        tools["adjust_resources"].invoke({
            "knowledge_change": -10,  # clamped to -3
            "reason": "floor test",
        })
        assert state.knowledge == 1  # 4 + (-3) = 1

    def test_close_deal(self):
        state = new_game("dealmaker")
        tools = self._tools(state)
        result = tools["close_deal"].invoke({
            "company_name": "NordTech",
            "country": "Estonia",
            "sector": "software",
            "entry_price": 20_000,
            "entry_multiple": 6.0,
            "revenue": 10_000_000,
            "ebitda": 2_000_000,
        })
        assert state.deals_closed == 1
        assert len(state.portfolio) == 1
        assert state.capital == 30_000
        assert "NordTech" in result

    def test_close_deal_insufficient_capital(self):
        state = new_game("investigator")
        tools = self._tools(state)
        result = tools["close_deal"].invoke({
            "company_name": "BigCo",
            "country": "Latvia",
            "sector": "industrials",
            "entry_price": 100_000,
            "entry_multiple": 7.0,
        })
        assert state.deals_closed == 0
        assert "Cannot close" in result

    def test_exit_deal(self):
        state = new_game("operator")
        state.portfolio = [{
            "name": "TestCo", "country": "Lithuania", "sector": "healthcare",
            "revenue": 5_000_000, "ebitda": 1_000_000,
            "entry_multiple": 5.0, "current_multiple": 5.0,
            "entry_price": 5_000_000, "current_value": 5_000_000,
        }]
        state.deals_closed = 1
        tools = self._tools(state)
        result = tools["exit_deal"].invoke({
            "company_name": "TestCo",
            "exit_multiple": 2.5,
            "exit_reason": "trade sale",
        })
        assert state.deals_exited == 1
        assert len(state.portfolio) == 0
        assert state.capital == 40_000 + 12_500_000

    def test_exit_deal_not_found(self):
        state = new_game("dealmaker")
        tools = self._tools(state)
        result = tools["exit_deal"].invoke({
            "company_name": "NonExistent",
            "exit_multiple": 2.0,
        })
        assert "not found" in result

    def test_screen_deal(self):
        state = new_game("dealmaker")
        tools = self._tools(state)
        tools["screen_deal"].invoke({
            "company_name": "BalticSoft",
            "country": "Latvia",
            "sector": "software",
            "revenue": 3_000_000,
            "ebitda": 500_000,
            "verdict": "promising",
        })
        assert state.deals_screened == 1

    def test_use_special_power(self):
        state = new_game("investigator")
        tools = self._tools(state)
        result = tools["use_special_power"].invoke({})
        assert state.special_power_used
        assert "Red Flag" in result

    def test_use_special_power_already_used(self):
        state = new_game("dealmaker")
        state.special_power_used = True
        tools = self._tools(state)
        result = tools["use_special_power"].invoke({})
        assert "already used" in result

    def test_update_portfolio_value(self):
        state = new_game("operator")
        state.portfolio = [{
            "name": "GrowCo", "country": "Estonia", "sector": "consumer",
            "revenue": 8_000_000, "ebitda": 1_500_000,
            "entry_multiple": 5.0, "current_multiple": 5.0,
            "entry_price": 7_500_000, "current_value": 7_500_000,
        }]
        tools = self._tools(state)
        tools["update_portfolio_value"].invoke({
            "company_name": "GrowCo",
            "new_multiple": 7.0,
            "reason": "margin improvement",
        })
        co = state.portfolio[0]
        assert co["current_multiple"] == 7.0
        assert co["current_value"] == int(7_500_000 * (7.0 / 5.0))

    def test_get_game_status(self):
        state = new_game("fundraiser")
        tools = self._tools(state)
        result = tools["get_game_status"].invoke({})
        assert "James Whitfield" in result
        assert "Round 1/5" in result

    def test_all_tools_built(self):
        state = new_game("dealmaker")
        from game.tools import build_game_tools
        tools = build_game_tools(state)
        assert len(tools) == 9
        names = {t.name for t in tools}
        assert names == {
            "advance_stage", "adjust_resources", "close_deal", "exit_deal",
            "screen_deal", "use_special_power", "update_portfolio_value",
            "get_game_status", "browse_pipeline",
        }

    def test_browse_pipeline_returns_matches(self):
        state = new_game("analyst")
        state.deal_pipeline = [
            {"name": "Vinted, UAB", "city": "Vilnius", "country": "LT",
             "sector": "Software", "sub_sector": "E-Commerce", "revenue": 999_000_000,
             "ebitda": 127_000_000, "ev": 1_998_000_000, "multiple": 15.7,
             "employees": 2000, "founded": 2008, "ownership": "vc backed",
             "description": "Online marketplace"},
            {"name": "Hollister Lietuva, UAB", "city": "Kaunas", "country": "LT",
             "sector": "Industrials", "sub_sector": "Manufacturing", "revenue": 133_000_000,
             "ebitda": 31_800_000, "ev": 160_000_000, "multiple": 5.0,
             "employees": 500, "founded": 2005, "ownership": "corporate",
             "description": "Medical devices"},
        ]
        from game.tools import build_game_tools
        tools = build_game_tools(state)
        browse = [t for t in tools if t.name == "browse_pipeline"][0]

        result = browse.invoke({"sector": "", "min_revenue": 0, "max_ev": 0})
        assert "Vinted" in result
        assert "Hollister" in result

        result = browse.invoke({"sector": "Software", "min_revenue": 0, "max_ev": 0})
        assert "Vinted" in result
        assert "Hollister" not in result

        result = browse.invoke({"sector": "", "min_revenue": 0, "max_ev": 200_000_000})
        assert "Hollister" in result
        assert "Vinted" not in result

    def test_browse_pipeline_empty(self):
        state = new_game("analyst")
        state.deal_pipeline = []
        from game.tools import build_game_tools
        tools = build_game_tools(state)
        browse = [t for t in tools if t.name == "browse_pipeline"][0]
        result = browse.invoke({"sector": "Pharma", "min_revenue": 0, "max_ev": 0})
        assert "No companies" in result


# ───────────────────────────────── Reset route test ──────────────────────────

class TestResetRoute:
    @pytest.mark.asyncio
    async def test_reset_endpoint_clears_session(self):
        from game.routes import register_game_routes
        captured = {}
        def fake_rt(path, methods=None):
            def decorator(fn):
                captured[path] = fn
                return fn
            return decorator
        register_game_routes(fake_rt)
        handler = captured["/app/training/reset"]

        sess = {
            "pe_hero_state": json.dumps(new_game("dealmaker").to_dict()),
            "pe_hero_level": "vp",
        }
        req = _FakeRequest(sess)
        response = await handler(req)
        assert response.status_code == 200
        body = json.loads(response.body)
        assert body["ok"] is True
        assert "pe_hero_state" not in sess
        assert "pe_hero_level" not in sess
