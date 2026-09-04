"""Unit/integration tests for ShareService."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.scenario import Scenario
from app.db.models.share import PlaythroughShare
from app.exceptions.playthrough_exceptions import (
    InvalidShareTokenError,
    PlaythroughAccessDeniedError,
)
from app.models.playthrough import PlaythroughCreate
from app.repositories.condition_repo import ConditionRepo
from app.repositories.end_condition_repo import EndConditionRepo
from app.repositories.entity_repo import EntityRepo
from app.repositories.invariant_repo import InvariantRepo
from app.repositories.map_repo import MapRepo
from app.repositories.participant_repo import ParticipantRepo
from app.repositories.playthrough_repo import PlaythroughRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.repositories.share_repo import ShareRepo
from app.repositories.turn_log_repo import TurnLogRepo
from app.repositories.user_repo import UserRepo
from app.services.playthrough_service import PlaythroughService
from app.services.share_service import ShareService, build_share_url


async def _make_share_service(db_session: AsyncSession) -> ShareService:
    return ShareService(
        share_repo=ShareRepo(db_session),
        playthrough_repo=PlaythroughRepo(db_session),
        participant_repo=ParticipantRepo(db_session),
    )


async def _seed_playthrough_with_owner(db_session: AsyncSession):
    user = await UserRepo(db_session).create(
        auth_provider_id=f"dev-auth-{uuid.uuid4()}", display_name="Owner"
    )
    scenario = Scenario(
        creator_id=user.user_id,
        title="Test Scenario",
        mode="newbie",
        complexity_tier="newbie",
        player_count_support="both",
        status="published",
    )
    db_session.add(scenario)
    await db_session.flush()

    playthrough_service = PlaythroughService(
        playthrough_repo=PlaythroughRepo(db_session),
        participant_repo=ParticipantRepo(db_session),
        scenario_repo=ScenarioRepo(db_session),
        share_repo=ShareRepo(db_session),
        turn_log_repo=TurnLogRepo(db_session),
        entity_repo=EntityRepo(db_session),
        condition_repo=ConditionRepo(db_session),
        invariant_repo=InvariantRepo(db_session),
        end_condition_repo=EndConditionRepo(db_session),
        map_repo=MapRepo(db_session),
    )
    response = await playthrough_service.create_playthrough(
        user_id=user.user_id,
        data=PlaythroughCreate(scenario_id=scenario.scenario_id, setup_values={}),
    )
    playthrough = await PlaythroughRepo(db_session).get_by_id(response.playthrough_id)
    return playthrough, user


@pytest.mark.asyncio
async def test_create_share_returns_new_token(db_session: AsyncSession):
    playthrough, user = await _seed_playthrough_with_owner(db_session)
    service = await _make_share_service(db_session)

    share = await service.create_share(
        playthrough_id=playthrough.playthrough_id, mode="spectate", user_id=user.user_id
    )

    assert share.mode == "spectate"
    assert share.playthrough_id == playthrough.playthrough_id
    assert len(share.share_token) > 20


@pytest.mark.asyncio
async def test_create_share_returns_existing_token_for_same_mode(
    db_session: AsyncSession,
):
    playthrough, user = await _seed_playthrough_with_owner(db_session)
    service = await _make_share_service(db_session)

    first = await service.create_share(
        playthrough_id=playthrough.playthrough_id, mode="join", user_id=user.user_id
    )
    second = await service.create_share(
        playthrough_id=playthrough.playthrough_id, mode="join", user_id=user.user_id
    )

    assert first.share_token == second.share_token


@pytest.mark.asyncio
async def test_create_share_denies_non_participant(db_session: AsyncSession):
    playthrough, _owner = await _seed_playthrough_with_owner(db_session)
    other_user = await UserRepo(db_session).create(
        auth_provider_id=f"dev-auth-{uuid.uuid4()}", display_name="Outsider"
    )
    service = await _make_share_service(db_session)

    with pytest.raises(PlaythroughAccessDeniedError):
        await service.create_share(
            playthrough_id=playthrough.playthrough_id,
            mode="spectate",
            user_id=other_user.user_id,
        )


@pytest.mark.asyncio
async def test_validate_token_raises_for_unknown_token(db_session: AsyncSession):
    service = await _make_share_service(db_session)

    with pytest.raises(InvalidShareTokenError):
        await service.validate_token("nonexistent-token")


@pytest.mark.asyncio
async def test_validate_token_raises_for_mode_mismatch(db_session: AsyncSession):
    playthrough, user = await _seed_playthrough_with_owner(db_session)
    service = await _make_share_service(db_session)
    share = await service.create_share(
        playthrough_id=playthrough.playthrough_id, mode="spectate", user_id=user.user_id
    )

    with pytest.raises(InvalidShareTokenError):
        await service.validate_token(share.share_token, required_mode="join")


def test_build_share_url_spectate_mode():
    fake_share = PlaythroughShare(
        playthrough_id=uuid.uuid4(), mode="spectate", share_token="abc123"
    )
    url = build_share_url(fake_share)
    assert "abc123" in url
    assert "/spectate/" in url


def test_build_share_url_join_mode():
    fake_share = PlaythroughShare(
        playthrough_id=uuid.uuid4(), mode="join", share_token="xyz789"
    )
    url = build_share_url(fake_share)
    assert "xyz789" in url
    assert "/join" in url
