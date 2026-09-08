"""Integration tests for ScenarioMusicRepo against a real test database."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.scenario import Scenario
from app.repositories.scenario_music_repo import ScenarioMusicRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.repositories.user_repo import UserRepo


async def _create_scenario(db_session: AsyncSession) -> Scenario:
    user = await UserRepo(db_session).create(
        auth_provider_id=f"dev-auth-{uuid.uuid4()}", display_name="Creator"
    )
    scenario = Scenario(
        creator_id=user.user_id,
        title="Test Scenario",
        mode="master",
        complexity_tier="master",
        player_count_support="solo",
    )
    return await ScenarioRepo(db_session).create(scenario)


@pytest.mark.asyncio
async def test_upsert_creates_then_overwrites(db_session: AsyncSession):
    scenario = await _create_scenario(db_session)
    repo = ScenarioMusicRepo(db_session)

    created = await repo.upsert(
        scenario.scenario_id, "peaceful", source="default", track_url=None
    )
    assert created.source == "default"
    assert created.track_url is None

    overwritten = await repo.upsert(
        scenario.scenario_id,
        "peaceful",
        source="upload",
        track_url="https://example.com/track.wav",
    )
    assert overwritten.scenario_music_id == created.scenario_music_id
    assert overwritten.source == "upload"
    assert overwritten.track_url == "https://example.com/track.wav"


@pytest.mark.asyncio
async def test_count_filled_slots(db_session: AsyncSession):
    scenario = await _create_scenario(db_session)
    repo = ScenarioMusicRepo(db_session)
    assert await repo.count_filled_slots(scenario.scenario_id) == 0

    await repo.upsert(
        scenario.scenario_id, "peaceful", source="default", track_url=None
    )
    await repo.upsert(scenario.scenario_id, "combat", source="default", track_url=None)

    assert await repo.count_filled_slots(scenario.scenario_id) == 2


@pytest.mark.asyncio
async def test_get_by_scenario_and_mood_returns_none_when_unset(
    db_session: AsyncSession,
):
    scenario = await _create_scenario(db_session)
    repo = ScenarioMusicRepo(db_session)
    assert await repo.get_by_scenario_and_mood(scenario.scenario_id, "triumph") is None
