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


def _mock_llm_stream(response_text: str):
    """Return a mock LLM that streams the given text in chunks."""
    class FakeChunk:
        def __init__(self, text):
            self.content = text

    class FakeLLM:
        def stream(self, messages):
            words = response_text.split(" ")
            for i in range(0, len(words), 3):
                yield FakeChunk(" ".join(words[i:i+3]) + " ")

    return FakeLLM()


async def _run_training_chat(session: dict, msg: str, llm_response: str = "Test response. 1. **Option A** 2. **Option B** 3. **Option C**"):
    """Invoke training_chat and collect all SSE events."""
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

    with patch("utils.llm.build_llm",
               return_value=_mock_llm_stream(llm_response)):
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
            llm_response="Great move! You pursued NordTech. stage complete Moving to Analysis. 1. **Build** model 2. **Review** data 3. **Call** management"
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
            llm_response="BOOM! Deal closed! You acquired NordTech. Investment made at 6x EBITDA. 1. **Optimize** ops 2. **Hire** CFO 3. **Expand** to Latvia"
        )
        updated = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert updated.deals_closed >= 1

    @pytest.mark.asyncio
    async def test_05_special_power_usage(self):
        state = new_game("dealmaker")
        assert not state.special_power_used
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(
            sess, "Use my special ability to bypass the gatekeeper",
            llm_response="Open Door activated! You reached the founder directly. 1. **Pitch** 2. **Negotiate** 3. **Walk**"
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
            llm_response="Stage complete! Moving to next round. Deal Sourcing begins. 1. **Scan** 2. **Follow-up** 3. **Network**"
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
            llm_response="Stage complete! What a run. 1. **Review** 2. **Celebrate** 3. **Replay**"
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
            llm_response="Excellent analysis! Knowledge +1. You spotted a revenue quality issue. 1. **Flag** 2. **Ignore** 3. **Investigate**"
        )
        updated = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert updated.knowledge == 5

    @pytest.mark.asyncio
    async def test_03_network_gain(self):
        state = new_game("analyst")
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(
            sess, "Attend Baltic PE conference",
            llm_response="Great networking! Network +1. You met a key LP. 1. **Follow-up** 2. **Pitch** 3. **Schedule**"
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
                llm_response=f"Stage complete! Moving to next stage. 1. **A** 2. **B** 3. **C**"
            )

        updated = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert updated.stage_idx == 4

    @pytest.mark.asyncio
    async def test_05_exit_increments(self):
        state = new_game("analyst")
        state.deals_closed = 1
        state.portfolio = [{"name": "TestCo", "current_value": 150_000}]
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(
            sess, "Exit TestCo via trade sale",
            llm_response="Sold the company for 3x MOIC! 1. **Reinvest** 2. **Distribute** 3. **Hold**"
        )
        updated = GameState.from_dict(json.loads(sess["pe_hero_state"]))
        assert updated.deals_exited >= 1

    @pytest.mark.asyncio
    async def test_06_game_over_after_all_rounds(self):
        state = new_game("analyst")
        state.round = 5
        state.stage_idx = 4
        state.deals_closed = 2
        sess = {"pe_hero_state": json.dumps(state.to_dict())}

        events, sess = await _run_training_chat(
            sess, "Final analysis",
            llm_response="Stage complete! The fund term ends. 1. **Review** 2. **Next** 3. **Done**"
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
            llm_response="Critical risk spotted! Revenue concentration at 80%. 1. **Walk** 2. **Renegotiate** 3. **Proceed**"
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
            llm_response="You already used it! 1. **A** 2. **B** 3. **C**"
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
            llm_response="Stage complete! Next round begins. 1. **A** 2. **B** 3. **C**"
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
            llm_response="Stage complete! 1. **Done** 2. **Review** 3. **Next**"
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
    async def test_tool_start_and_end_on_character_select(self):
        events, _ = await _run_training_chat(
            {}, "1",
            llm_response="Welcome! 1. **A** 2. **B** 3. **C**"
        )
        event_names = [n for n, _ in events]
        assert "tool_start" in event_names
        assert "tool_end" in event_names
        tool_start_idx = event_names.index("tool_start")
        tool_end_idx = event_names.index("tool_end")
        assert tool_start_idx < tool_end_idx

    @pytest.mark.asyncio
    async def test_tool_start_on_game_turn(self):
        state = new_game("dealmaker")
        sess = {"pe_hero_state": json.dumps(state.to_dict())}
        events, _ = await _run_training_chat(
            sess, "Do something",
            llm_response="Nice! 1. **A** 2. **B** 3. **C**"
        )
        event_names = [n for n, _ in events]
        assert "tool_start" in event_names


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
