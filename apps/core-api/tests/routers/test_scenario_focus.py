"""Integration tests for Scenario Focus endpoints and review turn-count gating."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.playthrough import Playthrough
from app.db.models.scenario import Scenario
from app.repositories.user_repo import UserRepo


@pytest.fixture
async def dev_user(db_session: AsyncSession):
    user_repo = UserRepo(db_session)
    return await user_repo.create(
        auth_provider_id=f"dev-auth-{uuid.uuid4()}", display_name="Dev Creator"
    )


@pytest.mark.asyncio
async def test_get_scenario_focus_details(
    async_client: AsyncClient,
    db_session: AsyncSession,
    dev_user,
) -> None:
    """Test retrieving scenario focus details including creator name and initial states."""
    scenario = Scenario(
        creator_id=dev_user.user_id,
        title="The Sunken Temple",
        mode="newbie",
        complexity_tier="newbie",
        player_count_support="solo",
        logline="Explore the flooded ruins of Eldoria.",
        world_data={"lore": "An ancient temple submerged in water."},
        setup_schema=[{"id": "name", "label": "Character Name", "type": "text"}],
        status="published",
    )
    db_session.add(scenario)
    await db_session.commit()

    response = await async_client.get(f"/v1/scenarios/{scenario.scenario_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "The Sunken Temple"
    assert data["creator_display_name"] == dev_user.display_name
    assert data["is_bookmarked"] is False
    assert data["can_review"] is False


@pytest.mark.asyncio
async def test_bookmark_toggle_flow(
    async_client: AsyncClient,
    db_session: AsyncSession,
    dev_user,
) -> None:
    """Test bookmarking and unbookmarking a scenario."""
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    scenario = Scenario(
        creator_id=dev_user.user_id,
        title="Crypt of Whispers",
        mode="newbie",
        complexity_tier="newbie",
        player_count_support="solo",
        status="published",
    )
    db_session.add(scenario)
    await db_session.commit()

    # Toggle Bookmark ON
    bm_res = await async_client.post(
        f"/v1/scenarios/{scenario.scenario_id}/bookmark",
        headers=headers,
    )
    assert bm_res.status_code == 200
    assert bm_res.json()["is_bookmarked"] is True

    # Check GET scenario response indicates is_bookmarked: True
    get_res = await async_client.get(
        f"/v1/scenarios/{scenario.scenario_id}", headers=headers
    )
    assert get_res.json()["is_bookmarked"] is True

    # Toggle Bookmark OFF
    bm_res_2 = await async_client.post(
        f"/v1/scenarios/{scenario.scenario_id}/bookmark",
        headers=headers,
    )
    assert bm_res_2.status_code == 200
    assert bm_res_2.json()["is_bookmarked"] is False


@pytest.mark.asyncio
async def test_review_submission_gating(
    async_client: AsyncClient,
    db_session: AsyncSession,
    dev_user,
) -> None:
    """Test that users with <10 turns are blocked and users with >=10 turns can post reviews."""
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    scenario = Scenario(
        creator_id=dev_user.user_id,
        title="Dragon's Peak",
        mode="newbie",
        complexity_tier="intermediate",
        player_count_support="solo",
        status="published",
    )
    db_session.add(scenario)
    await db_session.commit()

    # 1. Attempt to post review without any playthrough -> 403 Forbidden
    fail_res = await async_client.post(
        f"/v1/scenarios/{scenario.scenario_id}/reviews",
        json={"rating": 5, "comment": "Amazing scenario!"},
        headers=headers,
    )
    assert fail_res.status_code == 403

    # 2. Create playthrough with 5 turns -> still fails
    pt_short = Playthrough(
        scenario_id=scenario.scenario_id,
        created_by=dev_user.user_id,
        turn_count=5,
        status="active",
        scenario_version=1,
    )
    db_session.add(pt_short)
    await db_session.commit()

    fail_res_2 = await async_client.post(
        f"/v1/scenarios/{scenario.scenario_id}/reviews",
        json={"rating": 5, "comment": "Short run!"},
        headers=headers,
    )
    assert fail_res_2.status_code == 403

    # 3. Create playthrough with 12 turns -> succeeds
    pt_long = Playthrough(
        scenario_id=scenario.scenario_id,
        created_by=dev_user.user_id,
        turn_count=12,
        status="completed",
        scenario_version=1,
    )
    db_session.add(pt_long)
    await db_session.commit()

    success_res = await async_client.post(
        f"/v1/scenarios/{scenario.scenario_id}/reviews",
        json={"rating": 5, "comment": "Masterpiece adventure!"},
        headers=headers,
    )
    assert success_res.status_code == 201
    rev_data = success_res.json()
    assert rev_data["rating"] == 5
    assert rev_data["comment"] == "Masterpiece adventure!"

    # 4. GET reviews list
    list_res = await async_client.get(f"/v1/scenarios/{scenario.scenario_id}/reviews")
    assert list_res.status_code == 200
    reviews_list = list_res.json()
    assert reviews_list["total_count"] == 1
    assert reviews_list["items"][0]["comment"] == "Masterpiece adventure!"
