"""Integration tests for PlaythroughRepo against a real test Postgres instance."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.playthrough import Playthrough
from app.db.models.scenario import Scenario
from app.db.models.user import User
from app.repositories.playthrough_repo import PlaythroughRepo

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _seed_playthrough(session: AsyncSession) -> Playthrough:
    # IDs generated explicitly: the ORM column's default=uuid.uuid4 only fires
    # at flush/INSERT time, not at object construction, so it can't supply an
    # ID here before the related rows are built.
    user_id, scenario_id = uuid.uuid4(), uuid.uuid4()
    user = User(
        user_id=user_id, display_name="Tester", auth_provider_id=str(uuid.uuid4())
    )
    scenario = Scenario(
        scenario_id=scenario_id,
        creator_id=user_id,
        title="Test Scenario",
        mode="newbie",
        complexity_tier="newbie",
        player_count_support="solo",
    )
    session.add(user)
    await session.flush()
    session.add(scenario)
    await session.flush()

    playthrough = Playthrough(
        scenario_id=scenario_id,
        created_by=user_id,
        scenario_version=1,
        state={"setup": {}, "narrative": {"opening_prompt": None, "turns_so_far": []}},
    )
    session.add(playthrough)
    await session.flush()
    return playthrough


async def test_get_by_id_returns_playthrough(db_session: AsyncSession) -> None:
    playthrough = await _seed_playthrough(db_session)
    repo = PlaythroughRepo(db_session)

    fetched = await repo.get_by_id(playthrough.playthrough_id)

    assert fetched is not None
    assert fetched.playthrough_id == playthrough.playthrough_id


async def test_get_by_id_returns_none_for_unknown_id(db_session: AsyncSession) -> None:
    repo = PlaythroughRepo(db_session)

    fetched = await repo.get_by_id(uuid.uuid4())

    assert fetched is None


async def test_update_state_persists_new_state_and_turn_count(
    db_session: AsyncSession,
) -> None:
    playthrough = await _seed_playthrough(db_session)
    repo = PlaythroughRepo(db_session)
    new_state = {"setup": {}, "narrative": {"turns_so_far": [{"action_text": "look"}]}}

    await repo.update_state(playthrough.playthrough_id, new_state, 1)
    await db_session.flush()
    fetched = await repo.get_by_id(playthrough.playthrough_id)

    assert fetched is not None
    assert fetched.turn_count == 1
    assert fetched.state == new_state
