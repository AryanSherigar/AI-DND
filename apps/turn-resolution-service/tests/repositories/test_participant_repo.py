"""Integration tests for ParticipantRepo against a real test Postgres instance."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.participant import Participant
from app.db.models.playthrough import Playthrough
from app.db.models.scenario import Scenario
from app.db.models.user import User
from app.repositories.participant_repo import ParticipantRepo

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _seed_playthrough_with_participants(
    session: AsyncSession, participant_count: int = 1
) -> tuple[Playthrough, list[Participant]]:
    # IDs generated explicitly: the ORM column's default=uuid.uuid4 only fires
    # at flush/INSERT time, not at object construction.
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
        player_count_support="multiplayer",
    )
    session.add(user)
    await session.flush()
    session.add(scenario)
    await session.flush()

    playthrough = Playthrough(
        scenario_id=scenario_id, created_by=user_id, scenario_version=1
    )
    session.add(playthrough)
    await session.flush()

    participants = []
    for position in range(1, participant_count + 1):
        member_id = uuid.uuid4()
        member = User(
            user_id=member_id,
            display_name=f"Player {position}",
            auth_provider_id=str(uuid.uuid4()),
        )
        session.add(member)
        await session.flush()

        participant = Participant(
            playthrough_id=playthrough.playthrough_id,
            user_id=member_id,
            role="owner" if position == 1 else "joined",
            turn_order_position=position,
        )
        session.add(participant)
        participants.append(participant)
    await session.flush()

    return playthrough, participants


async def test_get_by_id_returns_participant(db_session: AsyncSession) -> None:
    _, participants = await _seed_playthrough_with_participants(db_session)
    repo = ParticipantRepo(db_session)

    fetched = await repo.get_by_id(participants[0].participant_id)

    assert fetched is not None
    assert fetched.participant_id == participants[0].participant_id


async def test_get_by_id_returns_none_for_unknown_id(db_session: AsyncSession) -> None:
    repo = ParticipantRepo(db_session)

    fetched = await repo.get_by_id(uuid.uuid4())

    assert fetched is None


async def test_list_by_playthrough_returns_all_participants(
    db_session: AsyncSession,
) -> None:
    playthrough, participants = await _seed_playthrough_with_participants(
        db_session, participant_count=3
    )
    repo = ParticipantRepo(db_session)

    fetched = await repo.list_by_playthrough(playthrough.playthrough_id)

    assert {p.participant_id for p in fetched} == {
        p.participant_id for p in participants
    }
