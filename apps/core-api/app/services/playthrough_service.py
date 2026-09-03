"""Playthrough domain service: creation, snapshotting, and access-gated reads."""

import uuid

import structlog

from app.db.models.participant import Participant
from app.db.models.playthrough import Playthrough
from app.db.models.scenario import Scenario
from app.exceptions.playthrough_exceptions import (
    InvalidSetupValuesError,
    InvalidShareTokenError,
    PlaythroughAccessDeniedError,
    PlaythroughMemoryCloneError,
    PlaythroughNotFoundError,
    PlaythroughNotJoinableError,
    ScenarioNotPublishedError,
    SoloScenarioJoinError,
)
from app.exceptions.scenario_exceptions import (
    ScenarioAccessDeniedError,
    ScenarioNotFoundError,
)
from app.integrations import memory_client
from app.logging_config import log_audit_event
from app.models.memory import MemoryTemplateCloneRequest
from app.models.playthrough import (
    ParticipantSummary,
    PlaythroughCreate,
    PlaythroughResponse,
)
from app.models.turn_log import TurnLogListResponse, TurnLogResponse
from app.repositories.condition_repo import ConditionRepo
from app.repositories.end_condition_repo import EndConditionRepo
from app.repositories.entity_repo import EntityRepo
from app.repositories.invariant_repo import InvariantRepo
from app.repositories.participant_repo import ParticipantRepo
from app.repositories.playthrough_repo import PlaythroughRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.repositories.share_repo import ShareRepo
from app.repositories.turn_log_repo import TurnLogRepo

logger = structlog.get_logger()

EVENT_PLAYTHROUGH_STARTED = "playthrough_started"


class PlaythroughService:
    """Service orchestrating playthrough creation and retrieval."""

    def __init__(
        self,
        playthrough_repo: PlaythroughRepo,
        participant_repo: ParticipantRepo,
        scenario_repo: ScenarioRepo,
        share_repo: ShareRepo,
        turn_log_repo: TurnLogRepo,
        entity_repo: EntityRepo,
        condition_repo: ConditionRepo,
        invariant_repo: InvariantRepo,
        end_condition_repo: EndConditionRepo,
    ) -> None:
        self.playthrough_repo = playthrough_repo
        self.participant_repo = participant_repo
        self.scenario_repo = scenario_repo
        self.share_repo = share_repo
        self.turn_log_repo = turn_log_repo
        self.entity_repo = entity_repo
        self.condition_repo = condition_repo
        self.invariant_repo = invariant_repo
        self.end_condition_repo = end_condition_repo

    async def create_playtest(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID
    ) -> PlaythroughResponse:
        """Start a playtest playthrough of the caller's own scenario.

        Reuses create_playthrough with is_playtest=True so playtest sessions
        run through the exact same pipeline as a real playthrough, but are
        excluded from discovery, play_count, and rating eligibility. Unlike a
        real playthrough, a playtest is allowed on a draft scenario and is
        restricted to the scenario's own creator.
        """
        scenario = await self.scenario_repo.get_by_id(scenario_id)
        if not scenario or scenario.status == "archived":
            raise ScenarioNotFoundError()
        if scenario.creator_id != user_id:
            raise ScenarioAccessDeniedError()

        return await self.create_playthrough(
            user_id=user_id,
            data=PlaythroughCreate(scenario_id=scenario_id),
            is_playtest=True,
        )

    async def create_playthrough(
        self,
        user_id: uuid.UUID,
        data: PlaythroughCreate,
        is_playtest: bool = False,
    ) -> PlaythroughResponse:
        """Create a playthrough: snapshot the scenario, seed state, clone memory."""
        scenario = await self.scenario_repo.get_by_id(data.scenario_id)
        if not scenario or scenario.status == "archived":
            raise ScenarioNotFoundError()
        if not is_playtest and scenario.status != "published":
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
            scenario_snapshot=await self._build_snapshot(scenario),
            is_playtest=is_playtest,
        )
        participant = Participant(
            playthrough_id=playthrough_id,
            user_id=user_id,
            role="owner",
            turn_order_position=1,
        )

        await self._clone_memory_space(scenario.scenario_id, playthrough_id)

        created = await self.playthrough_repo.create(playthrough)
        created_participant = await self.participant_repo.create(participant)
        log_audit_event(
            logger,
            EVENT_PLAYTHROUGH_STARTED,
            playthrough_id=str(playthrough_id),
            scenario_id=str(scenario.scenario_id),
        )
        return _to_response(
            created,
            scenario.title,
            created_participant.participant_id,
            [created_participant],
        )

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
        all_participants = await self.participant_repo.list_by_playthrough(
            playthrough_id
        )
        return _to_response(
            playthrough, scenario_title, participant.participant_id, all_participants
        )

    async def join_playthrough(
        self, share_token: str, user_id: uuid.UUID
    ) -> PlaythroughResponse:
        """Join a playthrough as a multiplayer participant via a join-mode token."""
        share = await self.share_repo.get_by_token(share_token)
        if share is None or share.mode != "join":
            raise InvalidShareTokenError()

        playthrough = await self.playthrough_repo.get_by_id(share.playthrough_id)
        if not playthrough:
            raise PlaythroughNotFoundError()
        if playthrough.status != "active":
            raise PlaythroughNotJoinableError()

        scenario = await self.scenario_repo.get_by_id(playthrough.scenario_id)
        if scenario and scenario.player_count_support == "solo":
            raise SoloScenarioJoinError()

        joined_participant = await self._join_as_participant(playthrough, user_id)
        all_participants = await self.participant_repo.list_by_playthrough(
            playthrough.playthrough_id
        )
        return _to_response(
            playthrough,
            scenario.title if scenario else "",
            joined_participant.participant_id,
            all_participants,
        )

    async def _join_as_participant(
        self, playthrough: Playthrough, user_id: uuid.UUID
    ) -> Participant:
        """Add user_id as a participant, no-op if they've already joined."""
        existing = await self.participant_repo.get_by_playthrough_and_user(
            playthrough.playthrough_id, user_id
        )
        if existing:
            return existing
        participants = await self.participant_repo.list_by_playthrough(
            playthrough.playthrough_id
        )
        participant = Participant(
            playthrough_id=playthrough.playthrough_id,
            user_id=user_id,
            role="joined",
            turn_order_position=len(participants) + 1,
        )
        return await self.participant_repo.create(participant)

    async def list_turns(
        self,
        playthrough_id: uuid.UUID,
        user_id: uuid.UUID | None,
        share_token: str | None,
        page: int,
        page_size: int,
        from_turn: int | None,
    ) -> TurnLogListResponse:
        """Fetch paginated turn history. Participants and share-token holders only."""
        if not await self.playthrough_repo.get_by_id(playthrough_id):
            raise PlaythroughNotFoundError()
        await self._require_turns_access(playthrough_id, user_id, share_token)

        items, total = await self.turn_log_repo.list_by_playthrough(
            playthrough_id,
            limit=page_size,
            offset=(page - 1) * page_size,
            from_turn=from_turn,
        )
        return TurnLogListResponse(
            items=[TurnLogResponse.model_validate(item) for item in items],
            total_count=total,
        )

    async def _require_turns_access(
        self,
        playthrough_id: uuid.UUID,
        user_id: uuid.UUID | None,
        share_token: str | None,
    ) -> None:
        if user_id is not None:
            participant = await self.participant_repo.get_by_playthrough_and_user(
                playthrough_id, user_id
            )
            if participant:
                return
        if share_token:
            share = await self.share_repo.get_by_token(share_token)
            if share and share.playthrough_id == playthrough_id:
                return
        raise PlaythroughAccessDeniedError()

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

    async def _build_snapshot(self, scenario: Scenario) -> dict[str, object]:
        """Freeze the scenario content TRS and the frontend read for this
        playthrough (ADR-8).

        setup_schema is included alongside the fields ADR-8 names for TRS
        (narrator_persona, state_schema, end_conditions, checkpoints) because
        the same pinning principle applies to it: the play screen displays
        setup field labels from this snapshot, not from Scenario directly, so
        a later edit to the scenario's setup fields doesn't retroactively
        relabel an already-active playthrough.

        For master mode, also pins entity attributes_schema/obtainable/
        narrator_instruction, rule_invariants, scenario_conditions
        (including their state_mutation column), and end_conditions (sorted
        by the creator's explicit priority, ascending — the source of truth
        for end_condition_evaluator's "first match wins" rule,
        master-mode-end-conditions.spec.md) — TRS never reads Scenario or its
        sub-resource tables directly during a turn
        (master-mode-turn-pipeline.spec.md).
        """
        snapshot: dict[str, object] = {
            "mode": scenario.mode,
            "narrator_persona": scenario.narrator_persona,
            "world_data": scenario.world_data,
            "setup_schema": scenario.setup_schema,
            "state_schema": scenario.state_schema,
            "checkpoints": scenario.checkpoints,
        }
        if scenario.mode == "master":
            snapshot["entities"] = await self._snapshot_entities(scenario.scenario_id)
            snapshot["scenario_conditions"] = await self._snapshot_conditions(
                scenario.scenario_id
            )
            snapshot["rule_invariants"] = await self._snapshot_invariants(
                scenario.scenario_id
            )
            snapshot["end_conditions"] = await self._snapshot_end_conditions(
                scenario.scenario_id
            )
        return snapshot

    async def _snapshot_entities(
        self, scenario_id: uuid.UUID
    ) -> list[dict[str, object]]:
        entities = await self.entity_repo.list_by_scenario(scenario_id)
        return [
            {
                "entity_id": str(e.entity_id),
                "attributes_schema": e.attributes_schema,
                "obtainable": e.obtainable,
                "narrator_instruction": e.narrator_instruction,
            }
            for e in entities
        ]

    async def _snapshot_conditions(
        self, scenario_id: uuid.UUID
    ) -> list[dict[str, object]]:
        conditions = await self.condition_repo.list_by_scenario(scenario_id)
        return [
            {
                "label": c.label,
                "condition_expression": c.condition_expression,
                "narrator_instruction": c.narrator_instruction,
                "state_mutation": c.state_mutation,
            }
            for c in conditions
        ]

    async def _snapshot_end_conditions(
        self, scenario_id: uuid.UUID
    ) -> list[dict[str, object]]:
        end_conditions = await self.end_condition_repo.list_by_scenario(scenario_id)
        return [
            {
                "condition_expression": ec.condition_expression,
                "outcome_tag": ec.outcome_tag,
                "outcome_title": ec.outcome_title,
                "outcome_text": ec.outcome_text,
                "is_secret": ec.is_secret,
                "priority": ec.priority,
            }
            for ec in end_conditions
        ]

    async def _snapshot_invariants(
        self, scenario_id: uuid.UUID
    ) -> list[dict[str, object]]:
        invariants = await self.invariant_repo.list_by_scenario(scenario_id)
        return [
            {
                "label": i.label,
                "invariant_expression": i.invariant_expression,
                "applies_to": i.applies_to,
                "narrator_text": i.narrator_text,
            }
            for i in invariants
        ]


def _validate_setup_values(
    setup_schema: list[object], setup_values: dict[str, object]
) -> None:
    """Validate submitted setup values against the scenario's setup_schema."""
    for field in setup_schema:
        if not isinstance(field, dict):
            continue
        _validate_single_field(field, setup_values)


def _validate_single_field(
    field: dict[str, object], setup_values: dict[str, object]
) -> None:
    """Validate a single setup schema field against submitted values."""
    field_key = str(field.get("field_key") or field.get("key") or field.get("id") or "")
    if not field_key:
        return
    is_required = bool(field.get("required", False))
    val = setup_values.get(field_key)

    if is_required and (val is None or val == "" or val == []):
        raise InvalidSetupValuesError(f"Missing required setup field: {field_key}")

    if val is None or val == "":
        return

    field_type = str(field.get("type") or "")
    if field_type in ("select", "single_select"):
        _validate_select_field(field_key, val, field.get("options"))
    elif field_type == "multi_select":
        _validate_multi_select_field(field_key, val, field.get("options"))


def _extract_option_values(options_raw: object) -> list[str]:
    """Extract string values from option list (strings or dicts)."""
    if not isinstance(options_raw, list):
        return []
    valid: list[str] = []
    for opt in options_raw:
        if isinstance(opt, str):
            valid.append(opt)
        elif isinstance(opt, dict) and "value" in opt:
            valid.append(str(opt["value"]))
    return valid


def _validate_select_field(field_key: str, val: object, options_raw: object) -> None:
    """Validate single-select value against options."""
    valid_options = _extract_option_values(options_raw)
    if valid_options and str(val) not in valid_options:
        raise InvalidSetupValuesError(
            f"Invalid value for setup field {field_key!r}: must be one of {valid_options}"
        )


def _validate_multi_select_field(
    field_key: str, val: object, options_raw: object
) -> None:
    """Validate multi-select array value against options."""
    valid_options = _extract_option_values(options_raw)
    if not valid_options:
        return
    selected = val if isinstance(val, list) else [val]
    for item in selected:
        if str(item) not in valid_options:
            raise InvalidSetupValuesError(
                f"Invalid selection {item!r} for setup field {field_key!r}"
            )


def _build_initial_state(setup_values: dict[str, object]) -> dict[str, object]:
    """Seed Playthrough.state. Newbie-mode only: opening prompt + setup values."""
    return {
        "setup": dict(setup_values),
        "narrative": {"opening_prompt": None, "turns_so_far": []},
    }


def _to_response(
    playthrough: Playthrough,
    scenario_title: str,
    participant_id: uuid.UUID,
    participants: list[Participant],
) -> PlaythroughResponse:
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
        is_playtest=playthrough.is_playtest,
        scenario_version=playthrough.scenario_version,
        scenario_snapshot=playthrough.scenario_snapshot,
        created_at=playthrough.created_at,
        updated_at=playthrough.updated_at,
        participant_id=participant_id,
        participants=[ParticipantSummary.model_validate(p) for p in participants],
    )
