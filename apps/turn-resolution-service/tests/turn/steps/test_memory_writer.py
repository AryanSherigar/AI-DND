"""Unit tests for memory_writer.py, with memory_client mocked."""

import uuid

import pytest

from app.config import settings
from app.models.turn import LoadedState, TurnRequest
from app.turn.steps import memory_writer


def _turn_request() -> TurnRequest:
    return TurnRequest(
        playthrough_id=uuid.uuid4(),
        participant_id=uuid.uuid4(),
        action_text="I look around.",
        turn_count=0,
    )


def _loaded_state() -> LoadedState:
    return LoadedState(
        scenario_id=uuid.uuid4(),
        scenario_snapshot={},
        state={"narrative": {"turns_so_far": []}},
        turn_count=0,
        checkpoint=None,
    )


def _turns(count: int) -> list[dict[str, object]]:
    return [
        {"action_text": f"action {i}", "narration_text": f"narration {i}"}
        for i in range(count)
    ]


async def test_maybe_flush_batch_fires_at_interval(monkeypatch) -> None:
    calls = []

    async def fake_ingest_batch(request):
        calls.append(request)

    monkeypatch.setattr(memory_writer.memory_client, "ingest_batch", fake_ingest_batch)

    await memory_writer.maybe_flush_batch(
        _turn_request(),
        _loaded_state(),
        settings.memory_batch_turn_interval,
        _turns(settings.memory_batch_turn_interval),
    )

    assert len(calls) == 1
    assert len(calls[0].turns_batch) == settings.memory_batch_turn_interval


@pytest.mark.parametrize("offset", [-1, 1])
async def test_maybe_flush_batch_skips_off_boundary(monkeypatch, offset: int) -> None:
    calls = []

    async def fake_ingest_batch(request):
        calls.append(request)

    monkeypatch.setattr(memory_writer.memory_client, "ingest_batch", fake_ingest_batch)

    await memory_writer.maybe_flush_batch(
        _turn_request(),
        _loaded_state(),
        settings.memory_batch_turn_interval + offset,
        _turns(settings.memory_batch_turn_interval),
    )

    assert calls == []


async def test_maybe_flush_batch_swallows_ingest_failure(monkeypatch) -> None:
    async def failing_ingest_batch(request):
        raise RuntimeError("simulated mock memory outage")

    monkeypatch.setattr(
        memory_writer.memory_client, "ingest_batch", failing_ingest_batch
    )

    await memory_writer.maybe_flush_batch(
        _turn_request(),
        _loaded_state(),
        settings.memory_batch_turn_interval,
        _turns(settings.memory_batch_turn_interval),
    )
    # No exception propagated — that's the assertion.
