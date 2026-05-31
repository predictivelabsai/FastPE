"""PE Hero game routes — training RPG at /app/training."""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from starlette.responses import StreamingResponse, JSONResponse

from chat import sse
from game.engine import (
    CHARACTERS, LEVELS, GameState, new_game, draw_event, format_status,
    STAGES, calculate_score,
)
from game.prompts import (
    GAME_MASTER_SYSTEM, WELCOME, CHARACTER_SELECT_ROW,
    GAME_OVER, LEVEL_UP_PROMPT,
)

log = logging.getLogger(__name__)

CHAR_MAP = {}
for k, v in CHARACTERS.items():
    CHAR_MAP[k] = k
    CHAR_MAP[v["name"].lower()] = k
    CHAR_MAP[v["title"].lower().lstrip("the ")] = k

CHAR_MAP.update({
    "1": "dealmaker", "2": "analyst", "3": "investigator",
    "4": "operator", "5": "fundraiser",
    "marcus": "dealmaker", "elena": "analyst", "raj": "investigator",
    "sofia": "operator", "james": "fundraiser",
    "marcus drake": "dealmaker", "elena voss": "analyst",
    "raj mehta": "investigator", "sofia chen": "operator",
    "james whitfield": "fundraiser",
})


def _get_game_state(sess) -> GameState | None:
    raw = sess.get("pe_hero_state")
    if raw:
        try:
            return GameState.from_dict(json.loads(raw) if isinstance(raw, str) else raw)
        except Exception:
            pass
    return None


def _save_game_state(sess, state: GameState):
    sess["pe_hero_state"] = json.dumps(state.to_dict())


def _build_system_prompt(state: GameState) -> str:
    char = CHARACTERS.get(state.character, {})
    lvl = LEVELS.get(state.level, {})
    event = draw_event()
    state.events_history.append(event["name"])

    char_info = (
        f"**{char['name']}** — {char['title']} ({char['icon']})\n"
        f"Role: {char['role']}\n"
        f"Ability: {char['ability']}\n"
        f"Background: {char['description']}"
    )

    return GAME_MASTER_SYSTEM.format(
        total_rounds=state.total_rounds,
        status=format_status(state),
        event=f"**{event['name']}**: {event['effect']}",
        character_info=char_info,
        level_title=lvl.get("title", "Associate"),
        level_complexity=lvl.get("complexity", ""),
    )


def _welcome_text() -> str:
    text = WELCOME
    for key, char in CHARACTERS.items():
        text += CHARACTER_SELECT_ROW.format(
            icon=char["icon"],
            name=char["name"],
            role=char["role"],
            capital=char["start_capital"],
            knowledge=char["start_knowledge"],
            network=char["start_network"],
            ability_short=char["ability"][:55] + "...",
        )
    text += "\n*Type a character name or number (1-5) to begin.*\n"
    return text


def _game_over_text(state: GameState) -> str:
    char = CHARACTERS.get(state.character, {})
    score = calculate_score(state)
    state.score = score

    if score >= 1200:
        result_tone = "WHAT A PERFORMANCE! You absolutely DOMINATED out there!"
    elif score >= 800:
        result_tone = "Solid run! You've got the instincts, now sharpen the execution."
    elif score >= 400:
        result_tone = "Not bad for a first run, but I KNOW you can do better. Get back in there!"
    else:
        result_tone = "Tough round. But hey, every great investor has a fund they'd rather forget. Learn and come back STRONGER."

    current_lvl = LEVELS[state.level]
    level_keys = list(LEVELS.keys())
    current_idx = level_keys.index(state.level)

    if current_idx < len(level_keys) - 1 and score >= LEVELS[level_keys[current_idx + 1]]["unlock"]:
        next_key = level_keys[current_idx + 1]
        next_lvl = LEVELS[next_key]
        next_level_msg = (
            f"\n**LEVEL UNLOCKED: {next_lvl['title']}** — {next_lvl['description']}\n\n"
            f"1. **Level up** to {next_lvl['title']} — let's GO!\n"
            f"2. **Replay** {current_lvl['title']} with a different character\n"
            f"3. **New game** — start fresh\n"
        )
    else:
        next_level_msg = (
            f"\nScore {LEVELS[level_keys[min(current_idx + 1, len(level_keys)-1)]]['unlock']:,} to unlock the next level.\n\n"
            f"1. **Replay** {current_lvl['title']} — come back stronger!\n"
            f"2. **New character** — try a different role\n"
            f"3. **New game** — start fresh\n"
        )

    return GAME_OVER.format(
        result_tone=result_tone,
        player_name=state.player_name,
        character_name=state.character_name,
        character_title=char.get("title", ""),
        portfolio_value=state.portfolio_value(),
        capital=state.capital,
        deals_closed=state.deals_closed,
        deals_exited=state.deals_exited,
        knowledge=state.knowledge,
        network=state.network,
        score=score,
        next_level_msg=next_level_msg,
    )


def register_game_routes(rt):
    """Register PE Hero training game routes."""

    @rt("/app/training/chat", methods=["POST"])
    async def training_chat(request):
        from starlette.requests import Request
        sess = request.session
        form = await request.form()
        user_msg = (form.get("msg") or "").strip()

        if not user_msg:
            return JSONResponse({"error": "empty message"}, status_code=400)

        state = _get_game_state(sess)

        async def event_stream():
            nonlocal state

            yield sse.event("session", {"sid": "training"})
            yield sse.event(sse.AGENT_ROUTE, {
                "slug": "pe_hero_game",
                "agent": "Coach V",
                "icon": "\U0001f3c8",
            })

            # ── Character selection ──
            if state is None:
                choice = user_msg.lower().strip().rstrip(".")
                char_key = CHAR_MAP.get(choice)

                # Check for level up command
                if choice in ("level up", "next level"):
                    yield sse.event(sse.TOKEN, {"text": _welcome_text()})
                    yield sse.event(sse.DONE, {"slug": "pe_hero_game"})
                    return

                if not char_key:
                    yield sse.event(sse.TOKEN, {"text": _welcome_text()})
                    yield sse.event(sse.DONE, {"slug": "pe_hero_game"})
                    return

                # Determine level from session
                level = sess.get("pe_hero_level", "associate")
                state = new_game(char_key, level=level, player_name=sess.get("email", "Player"))
                _save_game_state(sess, state)

                char = CHARACTERS[char_key]
                lvl = LEVELS[level]
                intro = (
                    f"## {char['icon']} You are **{char['name']}** — {char['title']}\n"
                    f"*{char['description']}*\n\n"
                    f"**€{char['start_capital']:,}** capital | "
                    f"**{char['start_knowledge']}** knowledge | "
                    f"**{char['start_network']}** network\n\n"
                    f"Special: *{char['ability']}*\n\n"
                    f"**Level: {lvl['title']}** — {lvl['description']}\n\n"
                    f"---\n\n"
                )
                yield sse.event(sse.TOKEN, {"text": intro})

                yield sse.event(sse.TOOL_START, {
                    "name": "coach_v",
                    "args": {"action": "Starting Round 1", "stage": "Deal Sourcing"},
                })
                system = _build_system_prompt(state)
                try:
                    from utils.llm import build_llm
                    llm = build_llm()
                    messages = [
                        SystemMessage(content=system),
                        HumanMessage(content=(
                            f"The game begins! Present Round 1, Stage 1: Deal Sourcing.\n"
                            f"Set the scene — the player just joined a Baltic PE fund. "
                            f"Show 3-4 potential deals in the pipeline with company names, countries, sectors, revenues.\n"
                            f"Give your coaching intro — fire them up! Then end with 3 choices."
                        )),
                    ]
                    first_chunk = True
                    for chunk in llm.stream(messages):
                        if hasattr(chunk, "content") and chunk.content:
                            if first_chunk:
                                yield sse.event(sse.TOOL_END, {"name": "coach_v", "output": ""})
                                first_chunk = False
                            yield sse.event(sse.TOKEN, {"text": chunk.content})
                except Exception as e:
                    log.exception("Game master LLM failed")
                    yield sse.event(sse.ERROR, {"message": str(e)})

                _save_game_state(sess, state)
                yield sse.event(sse.DONE, {"slug": "pe_hero_game"})
                return

            # ── Handle meta commands ──
            lower = user_msg.lower().strip()
            if lower in ("new game", "restart", "reset"):
                sess.pop("pe_hero_state", None)
                yield sse.event(sse.TOKEN, {"text": "Game reset! Let's go again.\n\n" + _welcome_text()})
                yield sse.event(sse.DONE, {"slug": "pe_hero_game"})
                return

            if lower in ("level up", "next level"):
                level_keys = list(LEVELS.keys())
                current_idx = level_keys.index(state.level)
                if current_idx < len(level_keys) - 1:
                    next_key = level_keys[current_idx + 1]
                    if state.score >= LEVELS[next_key]["unlock"]:
                        sess["pe_hero_level"] = next_key
                        sess.pop("pe_hero_state", None)
                        next_lvl = LEVELS[next_key]
                        yield sse.event(sse.TOKEN, {
                            "text": (
                                f"## LEVEL UP!\n\n"
                                f"Welcome to **{next_lvl['title']}** — {next_lvl['description']}\n\n"
                                f"*{next_lvl['complexity']}*\n\n"
                                f"Pick your character for this level:\n\n" + _welcome_text()
                            ),
                        })
                        yield sse.event(sse.DONE, {"slug": "pe_hero_game"})
                        return
                yield sse.event(sse.TOKEN, {"text": "You haven't unlocked the next level yet. Keep playing!\n"})
                yield sse.event(sse.DONE, {"slug": "pe_hero_game"})
                return

            # ── Game over ──
            if state.game_over:
                if lower in ("replay", "new character", "new game"):
                    sess.pop("pe_hero_state", None)
                    yield sse.event(sse.TOKEN, {"text": _welcome_text()})
                else:
                    yield sse.event(sse.TOKEN, {"text": _game_over_text(state)})
                yield sse.event(sse.DONE, {"slug": "pe_hero_game"})
                return

            # ── Normal game turn ──
            yield sse.event(sse.TOOL_START, {
                "name": "coach_v",
                "args": {
                    "action": user_msg[:40],
                    "stage": state.current_stage(),
                    "round": state.round,
                },
            })

            system = _build_system_prompt(state)
            messages = [
                SystemMessage(content=system),
                HumanMessage(content=(
                    f"Player action: {user_msg}\n\n"
                    f"Process this for {state.current_stage()} (Round {state.round}/{state.total_rounds}).\n"
                    f"React to their choice — give coaching feedback (praise great moves, roast bad ones).\n"
                    f"Show the outcome with updated resource numbers.\n"
                    f"Then present 3 new choices for the next action."
                )),
            ]

            accumulated = []
            try:
                from utils.llm import build_llm
                llm = build_llm()
                first_chunk = True
                for chunk in llm.stream(messages):
                    if hasattr(chunk, "content") and chunk.content:
                        if first_chunk:
                            yield sse.event(sse.TOOL_END, {"name": "coach_v", "output": ""})
                            first_chunk = False
                        accumulated.append(chunk.content)
                        yield sse.event(sse.TOKEN, {"text": chunk.content})
            except Exception as e:
                log.exception("Game master LLM failed")
                yield sse.event(sse.ERROR, {"message": str(e)})

            # Advance stage/round
            response_text = "".join(accumulated).lower()
            if any(kw in response_text for kw in ["next stage", "stage complete", "moving to", "advance to", "moving on"]):
                state.stage_idx += 1
                if state.stage_idx >= len(STAGES):
                    state.stage_idx = 0
                    state.round += 1
                    state.special_power_used = False
                    if state.round > state.total_rounds:
                        state.game_over = True
                        state.score = calculate_score(state)

            if "special" in lower or "ability" in lower or "power" in lower:
                if not state.special_power_used:
                    state.special_power_used = True

            if any(kw in response_text for kw in ["deal closed", "acquired", "investment made", "signed"]):
                state.deals_closed += 1

            if any(kw in response_text for kw in ["exited", "sold the company", "ipo"]):
                state.deals_exited += 1

            if "+1 knowledge" in response_text or "knowledge +1" in response_text:
                state.knowledge += 1
            if "+1 network" in response_text or "network +1" in response_text:
                state.network += 1

            _save_game_state(sess, state)

            if state.game_over:
                yield sse.event(sse.TOKEN, {"text": "\n\n---\n\n" + _game_over_text(state)})

            yield sse.event(sse.DONE, {"slug": "pe_hero_game"})

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @rt("/app/training/reset", methods=["POST"])
    async def training_reset(request):
        request.session.pop("pe_hero_state", None)
        request.session.pop("pe_hero_level", None)
        return JSONResponse({"ok": True})
