"""Playthrough domain service: creation, snapshotting, and access-gated reads."""

import uuid

from app.db.models.participant import Participant
from app.db.models.playthrough import Playthrough
from app.db.models.scenario import Scenario
from app.exceptions.playthrough_exceptions import (
    InvalidSetupValuesError,
    PlaythroughAccessDeniedError,
    PlaythroughMemoryCloneError,
    PlaythroughNotFoundError,
    ScenarioNotPublishedError,
)
from app.exceptions.scenario_exceptions import ScenarioNotFoundError
from app.integrations import memory_client
from app.models.memory import MemoryTemplateCloneRequest
from app.models.playthrough import PlaythroughCreate, PlaythroughResponse
from app.repositories.participant_repo import ParticipantRepo
from app.repositories.playthrough_repo import PlaythroughRepo
from app.repositories.scenario_repo import ScenarioRepo


class PlaythroughService:
    """Service orchestrating playthrough creation and retrieval."""

    def __init__(
        self,
        playthrough_repo: PlaythroughRepo,
        participant_repo: ParticipantRepo,
        scenario_repo: ScenarioRepo,
    ) -> None:
        self.playthrough_repo = playthrough_repo
        self.participant_repo = participant_repo
        self.scenario_repo = scenario_repo

    async def create_playthrough(
        self, user_id: uuid.UUID, data: PlaythroughCreate
    ) -> PlaythroughResponse:
        """Create a playthrough: snapshot the scenario, seed state, clone memory."""
        scenario = await self.scenario_repo.get_by_id(data.scenario_id)
        if not scenario or scenario.status == "archived":
            raise ScenarioNotFoundError()
        if scenario.status != "published":
            raise ScenarioNotPublishedError()

        _validate_setup_values(scenario.setup_schema, data.setup_values)

        # Generated here, not left to the ORM column default: SQLAlchemy's
        # `default=uuid.uuid4` on Playthrough.playthrough_id only evaluates at
        # flush/INSERT time, not at object construction — so relying on it
        # would leave playthrough_id as None for the clone call below, which
        # must run before anything is added to the session (see the
        # atomicity note on _clone_memory_space).
        playthrough_id = uuid.uuid4()
        playthrough = Playthrough(
            playthrough_id=playthrough_id,
            scenario_id=scenario.scenario_id,
            created_by=user_id,
            state=_build_initial_state(data.setup_values),
            scenario_version=scenario.current_version,
            scenario_snapshot=_build_snapshot(scenario),
        )
        participant = Participant(
            playthrough_id=playthrough_id,
            user_id=user_id,
            role="owner",
            turn_order_position=1,
        )

        await self._clone_memory_space(scenario.scenario_id, playthrough_id)

        created = await self.playthrough_repo.create(playthrough)
        await self.participant_repo.create(participant)
        return _to_response(created, scenario.title)

    async def get_playthrough(
        self, playthrough_id: uuid.UUID, user_id: uuid.UUID
    ) -> PlaythroughResponse:
        """Fetch a playthrough, gated to its participants only."""
        playthrough = await self.playthrough_repo.get_by_id(playthrough_id)
        if not playthrough:
            raise PlaythroughNotFoundError()

        participant = await self.participant_repo.get_by_playthrough_and_user(
            playthrough_id, user_id
        )
        if not participant:
            raise PlaythroughAccessDeniedError()

        scenario = await self.scenario_repo.get_by_id(playthrough.scenario_id)
        scenario_title = scenario.title if scenario else ""
        return _to_response(playthrough, scenario_title)

    async def _clone_memory_space(
        self, scenario_id: uuid.UUID, playthrough_id: uuid.UUID
    ) -> None:
        """Trigger the memory-layer template clone before any DB write happens."""
        try:
            await memory_client.clone_template_memory_space(
                MemoryTemplateCloneRequest(
                    scenario_id=scenario_id, playthrough_id=playthrough_id
                )
            )
        except Exception as exc:
            raise PlaythroughMemoryCloneError(str(exc)) from exc


def _validate_setup_values(
    setup_schema: list[object], setup_values: dict[str, str]
) -> None:
    """Validate submitted setup values against the scenario's setup_schema."""
    for field in setup_schema:
        if not isinstance(field, dict):
            continue
        field_key = field.get("field_key")
        if field.get("required") and field_key not in setup_values:
            raise InvalidSetupValuesError(f"Missing required setup field: {field_key}")
        if field_key not in setup_values:
            continue
        if field.get("type") == "select":
            options = field.get("options") or []
            if setup_values[field_key] not in options:
                raise InvalidSetupValuesError(
                    f"Invalid value for setup field {field_key!r}: "
                    f"must be one of {options}"
                )


def _build_initial_state(setup_values: dict[str, str]) -> dict[str, object]:
    """Seed Playthrough.state. Newbie-mode only: opening prompt + setup values."""
    return {
        "setup": dict(setup_values),
        "narrative": {"opening_prompt": None, "turns_so_far": []},
    }


def _build_snapshot(scenario: Scenario) -> dict[str, object]:
    """Freeze the scenario content TRS reads during turns (ADR-8)."""
    return {
        "narrator_persona": scenario.narrator_persona,
        "world_data": scenario.world_data,
        "state_schema": scenario.state_schema,
        "end_conditions": scenario.end_conditions,
        "checkpoints": scenario.checkpoints,
        "active_conditions": [],
    }


def _to_response(playthrough: Playthrough, scenario_title: str) -> PlaythroughResponse:
    """Map a Playthrough ORM entity to its response schema."""
    return PlaythroughResponse(
        playthrough_id=playthrough.playthrough_id,
        scenario_id=playthrough.scenario_id,
        scenario_title=scenario_title,
        created_by=playthrough.created_by,
        state=playthrough.state,
        checkpoint=playthrough.checkpoint,
        turn_count=playthrough.turn_count,
        status=playthrough.status,
        scenario_version=playthrough.scenario_version,
        scenario_snapshot=playthrough.scenario_snapshot,
        created_at=playthrough.created_at,
        updated_at=playthrough.updated_at,
    )
