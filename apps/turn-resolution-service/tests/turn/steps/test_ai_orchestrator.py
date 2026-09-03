"""Unit tests for ai_orchestrator.py, with gemini_client mocked."""

import uuid

import pytest
from google.genai import types

from app.config import settings
from app.exceptions.turn_exceptions import (
    GeminiUnavailableError,
    NarrationGenerationError,
)
from app.models.memory import Fact, MemoryQueryResponse
from app.models.tool_call import MasterModeTurnResult
from app.models.turn import LoadedState, TurnRequest
from app.turn.steps import ai_orchestrator


def _turn_request() -> TurnRequest:
    return TurnRequest(
        playthrough_id=uuid.uuid4(),
        participant_id=uuid.uuid4(),
        action_text="I draw my sword.",
        turn_count=0,
    )


def _loaded_state() -> LoadedState:
    return LoadedState(
        scenario_id=uuid.uuid4(),
        scenario_snapshot={
            "narrator_persona": "A grim voice.",
            "world_data": "A dungeon.",
        },
        state={"narrative": {"turns_so_far": []}},
        turn_count=0,
        checkpoint=None,
    )


def _abstained_context() -> MemoryQueryResponse:
    return MemoryQueryResponse(facts=[], abstained=True, resolved_time_point=None)


def _context_with_facts() -> MemoryQueryResponse:
    return MemoryQueryResponse(
        facts=[
            Fact(
                fact_id=uuid.uuid4(),
                subject="the door",
                predicate="is",
                object="locked",
                confidence=0.9,
            )
        ],
        abstained=False,
        resolved_time_point=None,
    )


async def test_generate_narration_yields_all_chunks(monkeypatch) -> None:
    calls = []

    async def fake_stream(system_instruction: str, prompt: str, timeout_seconds: int):
        calls.append((system_instruction, prompt))
        for chunk in ["Hello, ", "adventurer."]:
            yield chunk

    monkeypatch.setattr(ai_orchestrator.gemini_client, "stream_narration", fake_stream)

    chunks = [
        chunk
        async for chunk in ai_orchestrator.generate_narration(
            _turn_request(), _loaded_state(), _abstained_context()
        )
    ]

    assert chunks == ["Hello, ", "adventurer."]
    system_instruction, prompt = calls[0]
    assert system_instruction == "A grim voice."
    assert "A grim voice." not in prompt


async def test_generate_narration_retries_then_succeeds(monkeypatch) -> None:
    attempts = {"count": 0}

    async def fake_stream(system_instruction: str, prompt: str, timeout_seconds: int):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise GeminiUnavailableError("simulated transient failure")
        yield "Recovered narration."

    monkeypatch.setattr(ai_orchestrator.gemini_client, "stream_narration", fake_stream)

    chunks = [
        chunk
        async for chunk in ai_orchestrator.generate_narration(
            _turn_request(), _loaded_state(), _abstained_context()
        )
    ]

    assert chunks == ["Recovered narration."]
    assert attempts["count"] == 2


async def test_generate_narration_raises_after_retries_exhausted(monkeypatch) -> None:
    async def always_unavailable(
        system_instruction: str, prompt: str, timeout_seconds: int
    ):
        raise GeminiUnavailableError("simulated transient failure")
        yield  # pragma: no cover - unreachable, keeps this an async generator

    monkeypatch.setattr(
        ai_orchestrator.gemini_client, "stream_narration", always_unavailable
    )

    chunks = []
    with pytest.raises(NarrationGenerationError):
        async for chunk in ai_orchestrator.generate_narration(
            _turn_request(), _loaded_state(), _abstained_context()
        ):
            chunks.append(chunk)

    assert chunks == [ai_orchestrator._DEGRADED_NARRATION_MESSAGE]


async def test_generate_narration_prompt_includes_retrieved_facts(monkeypatch) -> None:
    calls = []

    async def fake_stream(system_instruction: str, prompt: str, timeout_seconds: int):
        calls.append(prompt)
        yield "Narration."

    monkeypatch.setattr(ai_orchestrator.gemini_client, "stream_narration", fake_stream)

    [
        chunk
        async for chunk in ai_orchestrator.generate_narration(
            _turn_request(), _loaded_state(), _context_with_facts()
        )
    ]

    assert "Known world facts:" in calls[0]
    assert "the door is locked" in calls[0]


async def test_generate_narration_prompt_omits_facts_block_on_abstention(
    monkeypatch,
) -> None:
    calls = []

    async def fake_stream(system_instruction: str, prompt: str, timeout_seconds: int):
        calls.append(prompt)
        yield "Narration."

    monkeypatch.setattr(ai_orchestrator.gemini_client, "stream_narration", fake_stream)

    [
        chunk
        async for chunk in ai_orchestrator.generate_narration(
            _turn_request(), _loaded_state(), _abstained_context()
        )
    ]

    assert "Known world facts:" not in calls[0]


# --- Master mode: function-calling round-trip loop -------------------------


class _FakeCandidate:
    def __init__(self) -> None:
        self.content = "fake-model-turn-content"


class _FakeResponse:
    def __init__(self, function_calls: list[types.FunctionCall], text: str) -> None:
        self.function_calls = function_calls
        self.text = text
        self.candidates = [_FakeCandidate()]


def _master_loaded_state() -> LoadedState:
    return LoadedState(
        scenario_id=uuid.uuid4(),
        scenario_snapshot={
            "mode": "master",
            "narrator_persona": "Dry humor.",
            "world_data": {},
            "state_schema": {
                "flags": {
                    "type": "object",
                    "fields": {
                        "investigated_lore": {"type": "boolean", "initial": False}
                    },
                }
            },
            "entities": [],
            "rule_invariants": [],
            "scenario_conditions": [],
        },
        state={
            "flags": {"investigated_lore": False},
            "narrative": {"turns_so_far": []},
        },
        turn_count=0,
        checkpoint=None,
    )


async def test_generate_narration_master_mode_tool_loop(monkeypatch) -> None:
    responses = [
        _FakeResponse(
            [types.FunctionCall(name="roll_dice", args={"sides": 20, "modifier": 0})],
            "",
        ),
        _FakeResponse(
            [
                types.FunctionCall(
                    name="set_field",
                    args={"path": "flags.investigated_lore", "value": "true"},
                )
            ],
            "",
        ),
        _FakeResponse([], "You find a clue."),
    ]

    async def fake_generate_with_tools(
        system_instruction, contents, timeout_seconds, tools
    ):
        return responses.pop(0)

    monkeypatch.setattr(
        ai_orchestrator.gemini_client, "generate_with_tools", fake_generate_with_tools
    )

    result_sink = MasterModeTurnResult(
        final_state={
            "flags": {"investigated_lore": False},
            "narrative": {"turns_so_far": []},
        }
    )
    chunks = [
        chunk
        async for chunk in ai_orchestrator.generate_narration(
            _turn_request(),
            _master_loaded_state(),
            _abstained_context(),
            [],
            result_sink,
        )
    ]

    assert "".join(chunks).strip() == "You find a clue."
    assert [tc.tool_name for tc in result_sink.tool_calls] == ["roll_dice", "set_field"]
    assert result_sink.tool_calls[0].is_valid is True
    assert result_sink.tool_calls[1].is_valid is True
    assert result_sink.final_state["flags"]["investigated_lore"] is True
    assert result_sink.mutated_paths == ["flags.investigated_lore"]


async def test_generate_narration_master_mode_rejects_invalid_mutation(
    monkeypatch,
) -> None:
    responses = [
        _FakeResponse(
            [
                types.FunctionCall(
                    name="set_field",
                    args={
                        "path": "flags.investigated_lore",
                        "value": "not-a-boolean-ish-value",
                    },
                )
            ],
            "",
        ),
        _FakeResponse([], "Nothing happens."),
    ]

    async def fake_generate_with_tools(
        system_instruction, contents, timeout_seconds, tools
    ):
        return responses.pop(0)

    monkeypatch.setattr(
        ai_orchestrator.gemini_client, "generate_with_tools", fake_generate_with_tools
    )

    result_sink = MasterModeTurnResult(
        final_state={
            "flags": {"investigated_lore": False},
            "narrative": {"turns_so_far": []},
        }
    )
    [
        chunk
        async for chunk in ai_orchestrator.generate_narration(
            _turn_request(),
            _master_loaded_state(),
            _abstained_context(),
            [],
            result_sink,
        )
    ]

    assert result_sink.tool_calls[0].is_valid is False
    assert result_sink.final_state["flags"]["investigated_lore"] is False
    assert result_sink.mutated_paths == []


async def test_generate_narration_master_mode_cap_hit(monkeypatch) -> None:
    call_count = {"n": 0}
    tools_seen: list[object] = []

    async def fake_generate_with_tools(
        system_instruction, contents, timeout_seconds, tools
    ):
        call_count["n"] += 1
        tools_seen.append(tools)
        if tools:
            return _FakeResponse(
                [types.FunctionCall(name="roll_dice", args={"sides": 6})], ""
            )
        return _FakeResponse([], "Finalized despite cap.")

    monkeypatch.setattr(
        ai_orchestrator.gemini_client, "generate_with_tools", fake_generate_with_tools
    )

    result_sink = MasterModeTurnResult(final_state={"narrative": {"turns_so_far": []}})
    chunks = [
        chunk
        async for chunk in ai_orchestrator.generate_narration(
            _turn_request(),
            _master_loaded_state(),
            _abstained_context(),
            [],
            result_sink,
        )
    ]

    assert "".join(chunks).strip() == "Finalized despite cap."
    assert call_count["n"] == settings.tool_call_max_round_trips + 1
    assert tools_seen[-1] is None


async def test_generate_narration_master_mode_includes_active_instructions_and_persona(
    monkeypatch,
) -> None:
    captured = {}

    async def fake_generate_with_tools(
        system_instruction, contents, timeout_seconds, tools
    ):
        captured["system_instruction"] = system_instruction
        return _FakeResponse([], "Narration.")

    monkeypatch.setattr(
        ai_orchestrator.gemini_client, "generate_with_tools", fake_generate_with_tools
    )

    result_sink = MasterModeTurnResult(final_state={"narrative": {"turns_so_far": []}})
    [
        chunk
        async for chunk in ai_orchestrator.generate_narration(
            _turn_request(),
            _master_loaded_state(),
            _abstained_context(),
            ["Kestrel Vane now travels with the player."],
            result_sink,
        )
    ]

    assert "Dry humor." in captured["system_instruction"]
    assert "Kestrel Vane now travels with the player." in captured["system_instruction"]
