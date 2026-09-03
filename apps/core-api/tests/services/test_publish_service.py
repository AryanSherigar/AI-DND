"""Unit/integration tests for PublishService."""

import uuid
from contextlib import asynccontextmanager

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.exceptions.scenario_exceptions import (
    ScenarioAccessDeniedError,
    ScenarioAlreadyPublishingError,
    ScenarioNotFoundError,
    ScenarioValidationError,
)
from app.integrations import memory_client
from app.models.entity import EntityCreate
from app.models.fact import FactCreate
from app.models.scenario import ScenarioCreate
from app.repositories.entity_repo import EntityRepo
from app.repositories.fact_repo import FactRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.repositories.user_repo import UserRepo
from app.services.entity_service import EntityService
from app.services.fact_service import FactService
from app.services.publish_service import PublishService, _check_content_tag
from app.services.scenario_service import ScenarioService


@pytest.fixture
async def sample_user(db_session: AsyncSession) -> User:
    user_repo = UserRepo(db_session)
    return await user_repo.create(
        auth_provider_id=f"test-auth-{uuid.uuid4()}", display_name="Creator User"
    )


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    user_repo = UserRepo(db_session)
    return await user_repo.create(
        auth_provider_id=f"test-auth-{uuid.uuid4()}", display_name="Other User"
    )


def _session_factory_for(session: AsyncSession):
    """Build a session-factory that reuses `session` instead of opening a new one.

    Keeps the background job on the same (uncommitted) test transaction so it
    can see rows the test set up earlier.
    """

    @asynccontextmanager
    async def _cm():
        yield session

    return lambda: _cm()


async def _create_draft(
    db_session: AsyncSession, user: User, content_tag: str | None = "all-ages"
):
    service = ScenarioService(ScenarioRepo(db_session))
    return await service.create_scenario(
        user.user_id,
        ScenarioCreate(
            title="Test Scenario",
            mode="newbie",
            complexity_tier="newbie",
            content_tag=content_tag,
        ),
    )


@pytest.mark.asyncio
async def test_start_publish_sets_status_publishing(
    db_session: AsyncSession, sample_user: User
):
    repo = ScenarioRepo(db_session)
    service = PublishService(repo)
    created = await _create_draft(db_session, sample_user)

    scenario = await service.start_publish(created.scenario_id, sample_user.user_id)

    assert scenario.status == "publishing"
    assert scenario.publish_error is None


@pytest.mark.asyncio
async def test_start_publish_rejects_non_creator(
    db_session: AsyncSession, sample_user: User, other_user: User
):
    repo = ScenarioRepo(db_session)
    service = PublishService(repo)
    created = await _create_draft(db_session, sample_user)

    with pytest.raises(ScenarioAccessDeniedError):
        await service.start_publish(created.scenario_id, other_user.user_id)


@pytest.mark.asyncio
async def test_start_publish_missing_scenario_404(
    db_session: AsyncSession, sample_user: User
):
    repo = ScenarioRepo(db_session)
    service = PublishService(repo)

    with pytest.raises(ScenarioNotFoundError):
        await service.start_publish(uuid.uuid4(), sample_user.user_id)


@pytest.mark.asyncio
async def test_start_publish_rejects_while_already_publishing(
    db_session: AsyncSession, sample_user: User
):
    repo = ScenarioRepo(db_session)
    service = PublishService(repo)
    created = await _create_draft(db_session, sample_user)
    await service.start_publish(created.scenario_id, sample_user.user_id)

    with pytest.raises(ScenarioAlreadyPublishingError):
        await service.start_publish(created.scenario_id, sample_user.user_id)


@pytest.mark.asyncio
async def test_run_publish_job_success_first_publish(
    db_session: AsyncSession, sample_user: User
):
    repo = ScenarioRepo(db_session)
    service = PublishService(repo)
    created = await _create_draft(db_session, sample_user, content_tag="all-ages")
    await service.start_publish(created.scenario_id, sample_user.user_id)

    await PublishService.run_publish_job(
        created.scenario_id, _session_factory_for(db_session)
    )

    published = await repo.get_by_id(created.scenario_id)
    assert published.status == "published"
    assert published.published_at is not None
    assert published.publish_error is None


@pytest.mark.asyncio
async def test_run_publish_job_first_failure_reverts_to_draft(
    db_session: AsyncSession, sample_user: User
):
    repo = ScenarioRepo(db_session)
    service = PublishService(repo)
    created = await _create_draft(db_session, sample_user, content_tag=None)
    await service.start_publish(created.scenario_id, sample_user.user_id)

    await PublishService.run_publish_job(
        created.scenario_id, _session_factory_for(db_session)
    )

    failed = await repo.get_by_id(created.scenario_id)
    assert failed.status == "draft"
    assert failed.published_at is None
    assert failed.publish_error is not None


@pytest.mark.asyncio
async def test_run_publish_job_republish_failure_keeps_scenario_live(
    db_session: AsyncSession, sample_user: User
):
    repo = ScenarioRepo(db_session)
    service = PublishService(repo)
    created = await _create_draft(db_session, sample_user, content_tag="all-ages")
    await service.start_publish(created.scenario_id, sample_user.user_id)
    await PublishService.run_publish_job(
        created.scenario_id, _session_factory_for(db_session)
    )

    # Creator clears the content tag, then re-publishes and it fails.
    scenario = await repo.get_by_id(created.scenario_id)
    scenario.content_tag = None
    await repo.update(scenario)
    await service.start_publish(created.scenario_id, sample_user.user_id)

    await PublishService.run_publish_job(
        created.scenario_id, _session_factory_for(db_session)
    )

    failed = await repo.get_by_id(created.scenario_id)
    assert failed.status == "publish_failed"
    assert failed.published_at is not None  # still considered live
    assert failed.publish_error is not None


async def _create_master_draft(db_session: AsyncSession, user: User):
    service = ScenarioService(ScenarioRepo(db_session))
    return await service.create_scenario(
        user.user_id,
        ScenarioCreate(
            title="The Hollow Cairn",
            mode="master",
            complexity_tier="master",
            content_tag="all-ages",
        ),
    )


def _capture_ingest_calls(monkeypatch):
    """Patch memory_client.ingest_scenario_template and return the list of
    requests it was called with, in order."""
    calls = []
    original = memory_client.ingest_scenario_template

    async def _spy(request):
        calls.append(request)
        return await original(request)

    monkeypatch.setattr(memory_client, "ingest_scenario_template", _spy)
    return calls


@pytest.mark.asyncio
async def test_run_publish_job_master_mode_sends_entities_and_facts(
    db_session: AsyncSession, sample_user: User, monkeypatch
):
    calls = _capture_ingest_calls(monkeypatch)
    service = PublishService(ScenarioRepo(db_session))
    created = await _create_master_draft(db_session, sample_user)

    entity_service = EntityService(EntityRepo(db_session), ScenarioRepo(db_session))
    warden = await entity_service.create_entity(
        created.scenario_id,
        sample_user.user_id,
        EntityCreate(entity_type="character", canonical_name="The Warden"),
    )
    sigil = await entity_service.create_entity(
        created.scenario_id,
        sample_user.user_id,
        EntityCreate(entity_type="item", canonical_name="Ember Sigil"),
    )
    fact_service = FactService(
        FactRepo(db_session), EntityRepo(db_session), ScenarioRepo(db_session)
    )
    await fact_service.create_fact(
        created.scenario_id,
        sample_user.user_id,
        FactCreate(
            subject_entity_id=warden.entity_id,
            predicate="vulnerable_to",
            object_entity_id=sigil.entity_id,
            hidden=True,
        ),
    )

    await service.start_publish(created.scenario_id, sample_user.user_id)
    await PublishService.run_publish_job(
        created.scenario_id, _session_factory_for(db_session)
    )

    assert len(calls) == 1
    request = calls[0]
    assert request.mode == "master"
    assert request.world_data == {}
    assert {e.entity_id for e in request.entities} == {
        warden.entity_id,
        sigil.entity_id,
    }
    assert len(request.facts) == 1
    fact = request.facts[0]
    assert fact.subject_entity_id == warden.entity_id
    assert fact.object_entity_id == sigil.entity_id
    assert fact.predicate == "vulnerable_to"
    assert fact.hidden is True  # hidden flag survives the ingest round-trip

    published = await ScenarioRepo(db_session).get_by_id(created.scenario_id)
    assert published.status == "published"


@pytest.mark.asyncio
async def test_run_publish_job_newbie_mode_sends_world_data_only(
    db_session: AsyncSession, sample_user: User, monkeypatch
):
    """Regression: newbie-mode publish is unchanged by the master-mode branch."""
    calls = _capture_ingest_calls(monkeypatch)
    service = PublishService(ScenarioRepo(db_session))
    created = await _create_draft(db_session, sample_user)
    await service.start_publish(created.scenario_id, sample_user.user_id)

    await PublishService.run_publish_job(
        created.scenario_id, _session_factory_for(db_session)
    )

    assert len(calls) == 1
    request = calls[0]
    assert request.mode == "newbie"
    assert request.entities == []
    assert request.facts == []


@pytest.mark.asyncio
async def test_run_publish_job_empty_master_mode_scenario_still_ingests(
    db_session: AsyncSession, sample_user: User, monkeypatch
):
    """A master-mode scenario with no entities/facts yet is still valid to
    publish — ingestion runs with empty lists, not skipped."""
    calls = _capture_ingest_calls(monkeypatch)
    service = PublishService(ScenarioRepo(db_session))
    created = await _create_master_draft(db_session, sample_user)
    await service.start_publish(created.scenario_id, sample_user.user_id)

    await PublishService.run_publish_job(
        created.scenario_id, _session_factory_for(db_session)
    )

    assert len(calls) == 1
    assert calls[0].mode == "master"
    assert calls[0].entities == []
    assert calls[0].facts == []

    published = await ScenarioRepo(db_session).get_by_id(created.scenario_id)
    assert published.status == "published"


def test_check_content_tag_raises_for_missing_or_invalid_tag():
    class _Fake:
        content_tag = None

    with pytest.raises(ScenarioValidationError):
        _check_content_tag(_Fake())

    _Fake.content_tag = "not-a-real-tag"
    with pytest.raises(ScenarioValidationError):
        _check_content_tag(_Fake())

    _Fake.content_tag = "all-ages"
    _check_content_tag(_Fake())  # does not raise
