"""Integration tests for minigame trigger/result-resolution wired into the
turn pipeline. Mirrors test_pipeline_end_conditions.py's conventions: mocks
Gemini via ai_orchestrator.gemini_client.generate_with_tools, runs against a
real test Postgres (db_session), never mocks the database.
"""

import json
import uuid

import pytest
from google.genai import types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.participant import Participant
from app.db.models.playthrough import Playthrough
from app.db.models.scenario import Scenario
from app.db.models.user import User
from app.exceptions.turn_exceptions import (
    MinigameResultMismatchError,
    MinigameResultRequiredError,
)
from app.models.auth import CurrentUser
from app.models.turn import TurnRequestInput
from app.turn import pipeline
from app.turn.steps import ai_orchestrator, end_condition_evaluator

pytestmark = pytest.mark.asyncio(loop_scope="session")


class _FakeCandidate:
    def __init__(self) -> None:
        self.content = "fake-model-turn-content"


class _FakeResponse:
    def __init__(self, function_calls: list[types.FunctionCall], text: str) -> None:
        self.function_calls = function_calls
        self.text = text
        self.candidates = [_FakeCandidate()]


def _fake_narration(text: str):
    async def _generate(system_instruction, contents, timeout_seconds, tools):
        return _FakeResponse([], text)

    return _generate


_WARDENS_ONSLAUGHT = {
    "minigame_id": "mg-wardens-onslaught",
    "minigame_type": "dodge",
    "label": "Warden's Onslaught",
    "trigger_condition_expression": {
        "field": "the_warden.health",
        "op": "<=",
        "value": 0,
    },
    "priority": 0,
    "outcome_mode": "binary",
    "win_mutation": {"path": "flags.tactical_advantage", "op": "set", "value": True},
    "lose_mutation": {"path": "player.health", "op": "decrement", "value": 15},
    "tiered_outcomes": [],
    "timeout_mutation": {"path": "player.health", "op": "decrement", "value": 5},
    "narrator_instruction_template": "The onslaught concludes: {outcome_tag}.",
    "dodge_config": {"difficulty": 3},
    "replit_embed_url": None,
}

_STATE_SCHEMA = {
    "player": {"type": "object", "fields": {"health": {"type": "number"}}},
    "flags": {"type": "object", "fields": {"tactical_advantage": {"type": "boolean"}}},
    "the_warden": {"type": "object", "fields": {"health": {"type": "number"}}},
}

_WARDEN_DEFEATED_END_CONDITION = {
    "condition_expression": {"field": "the_warden.health", "op": "<=", "value": 0},
    "outcome_tag": "win",
    "outcome_title": "The Ashen Ending",
    "outcome_text": "The Warden kneels.",
    "is_secret": False,
}


async def _seed_master_playthrough(
    session: AsyncSession,
    scenario_minigames: list[dict[str, object]],
    end_conditions: list[dict[str, object]] | None = None,
    state_overrides: dict[str, object] | None = None,
) -> tuple[Playthrough, Participant]:
    user_id, scenario_id = uuid.uuid4(), uuid.uuid4()
    user = User(
        user_id=user_id, display_name="Tester", auth_provider_id=str(uuid.uuid4())
    )
    scenario = Scenario(
        scenario_id=scenario_id,
        creator_id=user_id,
        title="The Hollow Cairn",
        mode="master",
        complexity_tier="master",
        player_count_support="solo",
    )
    state = {
        "the_warden": {"health": 0},
        "player": {"health": 100},
        "flags": {"tactical_advantage": False},
        "narrative": {"turns_so_far": []},
    }
    state.update(state_overrides or {})
    playthrough = Playthrough(
        scenario_id=scenario_id,
        created_by=user_id,
        scenario_version=1,
        scenario_snapshot={
            "mode": "master",
            "narrator_persona": "Dry, weary humor.",
            "world_data": {},
            "state_schema": _STATE_SCHEMA,
            "entities": [],
            "rule_invariants": [],
            "scenario_conditions": [],
            "end_conditions": end_conditions or [],
            "scenario_minigames": scenario_minigames,
        },
        state=state,
    )
    session.add(user)
    await session.flush()
    session.add(scenario)
    await session.flush()
    session.add(playthrough)
    await session.flush()

    participant = Participant(
        playthrough_id=playthrough.playthrough_id,
        user_id=user_id,
        role="owner",
        turn_order_position=1,
    )
    session.add(participant)
    await session.flush()

    return playthrough, participant


async def _add_second_participant(
    session: AsyncSession, playthrough_id: uuid.UUID
) -> Participant:
    second_user_id = uuid.uuid4()
    session.add(
        User(
            user_id=second_user_id,
            display_name="Second Tester",
            auth_provider_id=str(uuid.uuid4()),
        )
    )
    await session.flush()
    participant_two = Participant(
        playthrough_id=playthrough_id,
        user_id=second_user_id,
        role="joined",
        turn_order_position=2,
    )
    session.add(participant_two)
    await session.flush()
    return participant_two


async def _load_playthrough(
    session: AsyncSession, playthrough_id: uuid.UUID
) -> Playthrough:
    stmt = select(Playthrough).where(Playthrough.playthrough_id == playthrough_id)
    result = (await session.execute(stmt)).scalars().first()
    assert result is not None
    return result


async def test_minigame_trigger_yields_event_and_stamps_pending_state(
    db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(
        ai_orchestrator.gemini_client,
        "generate_with_tools",
        _fake_narration("The Warden staggers and falls."),
    )
    playthrough, participant = await _seed_master_playthrough(
        db_session, [_WARDENS_ONSLAUGHT]
    )

    turn_input = TurnRequestInput(
        playthrough_id=playthrough.playthrough_id,
        participant_id=participant.participant_id,
        action_text="I strike the final blow.",
    )
    response = await pipeline.run_turn(
        turn_input,
        db_session,
        CurrentUser(user_id=participant.user_id, token_version=1),
    )
    events = [event async for event in response.body_iterator]

    assert [e.event for e in events] == [
        "narration",
        "turn_summary",
        "minigame",
        "done",
    ]
    minigame_event = next(e for e in events if e.event == "minigame")
    payload = json.loads(minigame_event.data)
    assert payload["minigame_id"] == "mg-wardens-onslaught"
    assert payload["minigame_type"] == "dodge"
    assert payload["dodge_config"] == {"difficulty": 3}

    updated = await _load_playthrough(db_session, playthrough.playthrough_id)
    assert updated.state["_pending_minigame"]["minigame_id"] == "mg-wardens-onslaught"
    assert updated.status == "active"


async def test_minigame_event_payload_never_leaks_mutation_or_instruction_fields(
    db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(
        ai_orchestrator.gemini_client,
        "generate_with_tools",
        _fake_narration("The Warden falls."),
    )
    playthrough, participant = await _seed_master_playthrough(
        db_session, [_WARDENS_ONSLAUGHT]
    )

    turn_input = TurnRequestInput(
        playthrough_id=playthrough.playthrough_id,
        participant_id=participant.participant_id,
        action_text="I strike.",
    )
    response = await pipeline.run_turn(
        turn_input,
        db_session,
        CurrentUser(user_id=participant.user_id, token_version=1),
    )
    events = [event async for event in response.body_iterator]

    minigame_event = next(e for e in events if e.event == "minigame")
    for forbidden in (
        "win_mutation",
        "lose_mutation",
        "tiered_outcomes",
        "timeout_mutation",
        "narrator_instruction_template",
    ):
        assert forbidden not in minigame_event.data


async def test_solo_only_gate_suppresses_trigger_in_multiplayer(
    db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(
        ai_orchestrator.gemini_client,
        "generate_with_tools",
        _fake_narration("The Warden falls."),
    )
    playthrough, participant_one = await _seed_master_playthrough(
        db_session, [_WARDENS_ONSLAUGHT]
    )
    await _add_second_participant(db_session, playthrough.playthrough_id)

    turn_input = TurnRequestInput(
        playthrough_id=playthrough.playthrough_id,
        participant_id=participant_one.participant_id,
        action_text="I strike.",
    )
    response = await pipeline.run_turn(
        turn_input,
        db_session,
        CurrentUser(user_id=participant_one.user_id, token_version=1),
    )
    events = [event async for event in response.body_iterator]

    assert "minigame" not in [e.event for e in events]
    updated = await _load_playthrough(db_session, playthrough.playthrough_id)
    assert "_pending_minigame" not in updated.state


async def test_end_condition_suppressed_when_minigame_triggers_same_turn(
    db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(
        ai_orchestrator.gemini_client,
        "generate_with_tools",
        _fake_narration("The Warden falls."),
    )
    call_count = {"n": 0}
    original = end_condition_evaluator.evaluate_end_conditions

    def _counting_spy(*args, **kwargs):
        call_count["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        end_condition_evaluator, "evaluate_end_conditions", _counting_spy
    )

    playthrough, participant = await _seed_master_playthrough(
        db_session,
        [_WARDENS_ONSLAUGHT],
        end_conditions=[_WARDEN_DEFEATED_END_CONDITION],
    )

    turn_input = TurnRequestInput(
        playthrough_id=playthrough.playthrough_id,
        participant_id=participant.participant_id,
        action_text="I strike the final blow.",
    )
    response = await pipeline.run_turn(
        turn_input,
        db_session,
        CurrentUser(user_id=participant.user_id, token_version=1),
    )
    events = [event async for event in response.body_iterator]

    assert call_count["n"] == 0
    assert "minigame" in [e.event for e in events]
    assert "playthrough_ended" not in [e.event for e in events]

    updated = await _load_playthrough(db_session, playthrough.playthrough_id)
    assert updated.status == "active"


async def test_pending_minigame_rejects_normal_action(
    db_session: AsyncSession,
) -> None:
    playthrough, participant = await _seed_master_playthrough(
        db_session,
        [_WARDENS_ONSLAUGHT],
        state_overrides={
            "_pending_minigame": {
                "minigame_id": "mg-wardens-onslaught",
                "minigame_type": "dodge",
            }
        },
    )

    turn_input = TurnRequestInput(
        playthrough_id=playthrough.playthrough_id,
        participant_id=participant.participant_id,
        action_text="I try to just keep walking.",
    )

    with pytest.raises(MinigameResultRequiredError):
        await pipeline.run_turn(
            turn_input,
            db_session,
            CurrentUser(user_id=participant.user_id, token_version=1),
        )


async def test_mismatched_minigame_result_is_rejected(
    db_session: AsyncSession,
) -> None:
    playthrough, participant = await _seed_master_playthrough(
        db_session,
        [_WARDENS_ONSLAUGHT],
        state_overrides={
            "_pending_minigame": {
                "minigame_id": "mg-wardens-onslaught",
                "minigame_type": "dodge",
            }
        },
    )

    turn_input = TurnRequestInput(
        playthrough_id=playthrough.playthrough_id,
        participant_id=participant.participant_id,
        action_text="",
        action_kind="minigame_result",
        minigame_result={"minigame_id": "wrong-id", "outcome_tag": "win"},
    )

    with pytest.raises(MinigameResultMismatchError):
        await pipeline.run_turn(
            turn_input,
            db_session,
            CurrentUser(user_id=participant.user_id, token_version=1),
        )


async def test_minigame_result_submission_with_nothing_pending_is_rejected(
    db_session: AsyncSession,
) -> None:
    playthrough, participant = await _seed_master_playthrough(
        db_session, [_WARDENS_ONSLAUGHT]
    )

    turn_input = TurnRequestInput(
        playthrough_id=playthrough.playthrough_id,
        participant_id=participant.participant_id,
        action_text="",
        action_kind="minigame_result",
        minigame_result={"minigame_id": "mg-wardens-onslaught", "outcome_tag": "win"},
    )

    with pytest.raises(MinigameResultMismatchError):
        await pipeline.run_turn(
            turn_input,
            db_session,
            CurrentUser(user_id=participant.user_id, token_version=1),
        )


async def test_minigame_result_resolution_applies_mutation_and_clears_pending(
    db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(
        ai_orchestrator.gemini_client,
        "generate_with_tools",
        _fake_narration("You feel the tactical advantage settle in."),
    )
    # win_mutation also raises the_warden.health above 0, so the same
    # minigame's trigger_condition_expression ("the_warden.health <= 0")
    # no longer matches on the resolution turn itself.
    resolved_minigame = {
        **_WARDENS_ONSLAUGHT,
        "win_mutation": {"path": "the_warden.health", "op": "set", "value": 50},
    }
    playthrough, participant = await _seed_master_playthrough(
        db_session,
        [resolved_minigame],
        state_overrides={
            "_pending_minigame": {
                "minigame_id": "mg-wardens-onslaught",
                "minigame_type": "dodge",
            }
        },
    )

    turn_input = TurnRequestInput(
        playthrough_id=playthrough.playthrough_id,
        participant_id=participant.participant_id,
        action_text="",
        action_kind="minigame_result",
        minigame_result={"minigame_id": "mg-wardens-onslaught", "outcome_tag": "win"},
    )
    response = await pipeline.run_turn(
        turn_input,
        db_session,
        CurrentUser(user_id=participant.user_id, token_version=1),
    )
    events = [event async for event in response.body_iterator]

    assert "minigame" not in [e.event for e in events]

    updated = await _load_playthrough(db_session, playthrough.playthrough_id)
    assert "_pending_minigame" not in updated.state
    assert updated.state["the_warden"]["health"] == 50.0
