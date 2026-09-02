"""Unit tests for ai_orchestrator.py, with gemini_client mocked."""

import uuid

import pytest

from app.exceptions.turn_exceptions import (
    GeminiUnavailableError,
    NarrationGenerationError,
)
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
            _turn_request(), _loaded_state()
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
            _turn_request(), _loaded_state()
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
            _turn_request(), _loaded_state()
        ):
            chunks.append(chunk)

    assert chunks == [ai_orchestrator._DEGRADED_NARRATION_MESSAGE]
