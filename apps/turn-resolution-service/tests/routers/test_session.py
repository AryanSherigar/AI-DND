"""Integration tests for the session router's access gating, against real Postgres."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.participant import Participant
from app.db.models.playthrough import Playthrough
from app.db.models.scenario import Scenario
from app.db.models.share import PlaythroughShare
from app.db.models.user import User


async def _seed_playthrough_with_share(
    session: AsyncSession, mode: str = "spectate"
) -> tuple[Playthrough, Participant, PlaythroughShare]:
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
        player_count_support="both",
    )
    playthrough = Playthrough(
        scenario_id=scenario_id,
        created_by=user_id,
        scenario_version=1,
        scenario_snapshot={},
        state={"narrative": {"turns_so_far": []}},
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

    share = PlaythroughShare(
        playthrough_id=playthrough.playthrough_id,
        mode=mode,
        share_token=f"tok_{uuid.uuid4()}",
    )
    session.add(share)
    await session.flush()
    await session.commit()

    return playthrough, participant, share


async def test_spectate_rejects_unknown_token(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    playthrough, _participant, _share = await _seed_playthrough_with_share(db_session)

    response = await async_client.get(
        f"/v1/session/{playthrough.playthrough_id}/spectate",
        params={"share_token": "not-a-real-token"},
    )

    assert response.status_code == 403


async def test_spectate_rejects_join_mode_token(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    playthrough, _participant, share = await _seed_playthrough_with_share(
        db_session, mode="join"
    )

    response = await async_client.get(
        f"/v1/session/{playthrough.playthrough_id}/spectate",
        params={"share_token": share.share_token},
    )

    assert response.status_code == 403


async def test_notifications_requires_authentication(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    playthrough, participant, _share = await _seed_playthrough_with_share(db_session)

    response = await async_client.get(
        f"/v1/session/{playthrough.playthrough_id}/notifications",
        params={"participant_id": str(participant.participant_id)},
    )

    assert response.status_code == 401


async def test_notifications_rejects_mismatched_participant(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    playthrough, _participant, _share = await _seed_playthrough_with_share(db_session)
    unrelated_participant_id = uuid.uuid4()

    response = await async_client.get(
        f"/v1/session/{playthrough.playthrough_id}/notifications",
        params={"participant_id": str(unrelated_participant_id)},
        headers={"x-dev-user-id": str(uuid.uuid4())},
    )

    assert response.status_code == 404
