"""Unit tests for context_retrieval.py, with memory_client mocked."""

import uuid

from app.models.memory import MemoryQueryResponse
from app.models.turn import LoadedState, TurnRequest
from app.turn.steps import context_retrieval


def _turn_request() -> TurnRequest:
    return TurnRequest(
        playthrough_id=uuid.uuid4(),
        participant_id=uuid.uuid4(),
        action_text="I search the room.",
        turn_count=2,
    )


def _loaded_state() -> LoadedState:
    return LoadedState(
        scenario_id=uuid.uuid4(),
        scenario_snapshot={},
        state={"narrative": {"turns_so_far": []}},
        turn_count=2,
        checkpoint="chapter_1",
    )


async def test_retrieve_context_returns_query_response(monkeypatch) -> None:
    captured_requests = []
    expected = MemoryQueryResponse(facts=[], abstained=False, resolved_time_point="2")

    async def fake_query_memory(request):
        captured_requests.append(request)
        return expected

    monkeypatch.setattr(
        context_retrieval.memory_client, "query_memory", fake_query_memory
    )

    turn_request = _turn_request()
    loaded_state = _loaded_state()
    result = await context_retrieval.retrieve_context(turn_request, loaded_state)

    assert result is expected
    request = captured_requests[0]
    assert request.scenario_id == loaded_state.scenario_id
    assert request.playthrough_id == turn_request.playthrough_id
    assert request.participant_id == turn_request.participant_id
    assert request.query_text == turn_request.action_text
    assert request.checkpoint == loaded_state.checkpoint
    assert request.game_state == loaded_state.state
    assert request.as_of_turn == loaded_state.turn_count


async def test_retrieve_context_handles_abstention(monkeypatch) -> None:
    async def fake_query_memory(request):
        return MemoryQueryResponse(facts=[], abstained=True, resolved_time_point=None)

    monkeypatch.setattr(
        context_retrieval.memory_client, "query_memory", fake_query_memory
    )

    result = await context_retrieval.retrieve_context(_turn_request(), _loaded_state())

    assert result.abstained is True
    assert result.facts == []


async def test_retrieve_context_uses_empty_string_checkpoint_when_none(
    monkeypatch,
) -> None:
    captured_requests = []

    async def fake_query_memory(request):
        captured_requests.append(request)
        return MemoryQueryResponse(facts=[], abstained=True, resolved_time_point=None)

    monkeypatch.setattr(
        context_retrieval.memory_client, "query_memory", fake_query_memory
    )

    loaded_state = LoadedState(
        scenario_id=uuid.uuid4(),
        scenario_snapshot={},
        state={},
        turn_count=0,
        checkpoint=None,
    )
    await context_retrieval.retrieve_context(_turn_request(), loaded_state)

    assert captured_requests[0].checkpoint == ""
