"""Unit tests for state_loader.py, with the repository mocked."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.exceptions.turn_exceptions import PlaythroughNotActiveError
from app.turn.steps.state_loader import load_state


async def test_load_state_returns_snapshot_and_state() -> None:
    scenario_id = uuid.uuid4()
    playthrough_repo = AsyncMock()
    playthrough_repo.get_by_id.return_value = SimpleNamespace(
        scenario_id=scenario_id,
        scenario_snapshot={"narrator_persona": "A grim voice."},
        state={"narrative": {"turns_so_far": []}},
        turn_count=3,
        checkpoint="chapter_1",
    )

    loaded = await load_state(uuid.uuid4(), playthrough_repo)

    assert loaded.scenario_id == scenario_id
    assert loaded.scenario_snapshot == {"narrator_persona": "A grim voice."}
    assert loaded.turn_count == 3
    assert loaded.checkpoint == "chapter_1"


async def test_load_state_never_queries_scenario_repo_directly() -> None:
    """Confirms ADR-8: only playthrough_repo is touched, never a Scenario read."""
    playthrough_repo = AsyncMock()
    playthrough_repo.get_by_id.return_value = SimpleNamespace(
        scenario_id=uuid.uuid4(),
        scenario_snapshot={},
        state={},
        turn_count=0,
        checkpoint=None,
    )

    await load_state(uuid.uuid4(), playthrough_repo)

    playthrough_repo.get_by_id.assert_awaited_once()


async def test_load_state_raises_when_playthrough_missing() -> None:
    playthrough_repo = AsyncMock()
    playthrough_repo.get_by_id.return_value = None

    with pytest.raises(PlaythroughNotActiveError):
        await load_state(uuid.uuid4(), playthrough_repo)
