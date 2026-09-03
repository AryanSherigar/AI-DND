"""Publish flow orchestration: content-tag check + authoring-time memory ingestion.

Publish is two-phase: `start_publish` runs synchronously within the request
(validates + flips the scenario to 'publishing'), and `run_publish_job` runs
afterwards as a FastAPI BackgroundTask against its own DB session, since the
request-scoped session is gone by the time it executes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.entity import Entity
from app.db.models.fact import Fact
from app.db.models.scenario import Scenario
from app.exceptions.scenario_exceptions import (
    ScenarioAccessDeniedError,
    ScenarioAlreadyPublishingError,
    ScenarioNotFoundError,
    ScenarioValidationError,
)
from app.integrations import memory_client
from app.logging_config import log_audit_event
from app.models.memory import (
    EntityIngestPayload,
    FactIngestPayload,
    MemoryTemplateIngestRequest,
)
from app.repositories.entity_repo import EntityRepo
from app.repositories.fact_repo import FactRepo
from app.repositories.scenario_repo import ScenarioRepo

logger = structlog.get_logger()

ALLOWED_CONTENT_TAGS: set[str] = {"all-ages", "teen", "mature"}

EVENT_SCENARIO_PUBLISH_STARTED = "scenario_publish_started"
EVENT_SCENARIO_PUBLISH_COMPLETED = "scenario_publish_completed"
EVENT_SCENARIO_PUBLISH_FAILED = "scenario_publish_failed"


class PublishService:
    """Service orchestrating the two-phase publish flow."""

    def __init__(self, scenario_repo: ScenarioRepo) -> None:
        self.scenario_repo = scenario_repo

    async def start_publish(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID
    ) -> Scenario:
        """Validate ownership and flip the scenario to 'publishing'."""
        scenario = await self.scenario_repo.get_by_id(scenario_id)
        if not scenario or scenario.status == "archived":
            raise ScenarioNotFoundError()

        if scenario.creator_id != user_id:
            raise ScenarioAccessDeniedError()

        if scenario.status == "publishing":
            raise ScenarioAlreadyPublishingError()

        scenario.status = "publishing"
        scenario.publish_error = None
        updated = await self.scenario_repo.update(scenario)
        log_audit_event(
            logger,
            EVENT_SCENARIO_PUBLISH_STARTED,
            scenario_id=str(scenario_id),
            user_id=str(user_id),
        )
        # Must commit here rather than leaving it to the request-scoped
        # session's usual end-of-request commit: FastAPI runs BackgroundTasks
        # *before* a yield-dependency's post-yield cleanup code (including
        # get_db_session's commit) executes. Without an explicit commit now,
        # this row's UPDATE stays uncommitted (holding its row lock) while
        # run_publish_job's own session blocks trying to UPDATE the same
        # row — a deadlock between this request and the background job.
        await self.scenario_repo.session.commit()
        return updated

    @staticmethod
    async def run_publish_job(
        scenario_id: uuid.UUID,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Run the content-tag check and authoring-time ingestion in the background."""
        async with session_factory() as session:
            repo = ScenarioRepo(session)
            scenario = await repo.get_by_id(scenario_id)
            if scenario is None:
                return

            try:
                _check_content_tag(scenario)
                ingest_request = await _build_ingest_request(
                    scenario, EntityRepo(session), FactRepo(session)
                )
                await memory_client.ingest_scenario_template(ingest_request)
            except Exception as exc:  # noqa: BLE001 - captured for publish_error
                scenario.status = (
                    "draft" if scenario.published_at is None else "publish_failed"
                )
                scenario.publish_error = str(exc)
                log_audit_event(
                    logger,
                    EVENT_SCENARIO_PUBLISH_FAILED,
                    scenario_id=str(scenario_id),
                    error=str(exc),
                )
            else:
                scenario.status = "published"
                scenario.published_at = scenario.published_at or datetime.now(UTC)
                scenario.publish_error = None
                log_audit_event(
                    logger,
                    EVENT_SCENARIO_PUBLISH_COMPLETED,
                    scenario_id=str(scenario_id),
                )

            await session.commit()


def _check_content_tag(scenario: Scenario) -> None:
    """Validate the creator-declared content tag against the fixed taxonomy."""
    if not scenario.content_tag or scenario.content_tag not in ALLOWED_CONTENT_TAGS:
        raise ScenarioValidationError(
            f"content_tag must be one of {sorted(ALLOWED_CONTENT_TAGS)}, "
            f"got {scenario.content_tag!r}"
        )


async def _build_ingest_request(
    scenario: Scenario, entity_repo: EntityRepo, fact_repo: FactRepo
) -> MemoryTemplateIngestRequest:
    """Build the authoring-time ingestion request for a scenario's mode.

    master mode sends entities/facts (direct write, no LLM extraction);
    newbie mode sends world_data (LLM extraction) — mutually exclusive per
    master-mode-memory-contract.spec.md.
    """
    if scenario.mode == "master":
        entities = await entity_repo.list_by_scenario(scenario.scenario_id)
        facts = await fact_repo.list_by_scenario(scenario.scenario_id)
        return MemoryTemplateIngestRequest(
            scenario_id=scenario.scenario_id,
            mode="master",
            entities=[_to_entity_payload(e) for e in entities],
            facts=[_to_fact_payload(f) for f in facts],
        )
    return MemoryTemplateIngestRequest(
        scenario_id=scenario.scenario_id,
        mode="newbie",
        world_data=scenario.world_data,
    )


def _to_entity_payload(entity: Entity) -> EntityIngestPayload:
    return EntityIngestPayload(
        entity_id=entity.entity_id,
        entity_type=entity.entity_type,
        canonical_name=entity.canonical_name,
        aliases=entity.aliases,
        description=entity.description,
    )


def _to_fact_payload(fact: Fact) -> FactIngestPayload:
    return FactIngestPayload(
        fact_id=fact.fact_id,
        subject_entity_id=fact.subject_entity_id,
        predicate=fact.predicate,
        object_entity_id=fact.object_entity_id,
        object_literal=fact.object_literal,
        valid_from=fact.valid_from,
        when_active=fact.when_active,
        hidden=fact.hidden,
    )
