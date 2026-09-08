"""Minigame domain service handling business logic and scenario-ownership
rules.

Master-mode only: every public method starts by confirming the scenario
exists, is owned by the caller, and is a master-mode scenario
(_ensure_master_mode_owner) — mirrors MapService's guard name/shape
(docs/specs/master-mode-minigames.spec.md).
"""

import uuid
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError as PydanticValidationError
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

from app.db.models.scenario import Scenario
from app.db.models.scenario_minigame import ScenarioMinigame
from app.exceptions.minigame_exceptions import (
    MinigameModeError,
    MinigameNotFoundError,
    MinigameUnreachableError,
    MinigameValidationError,
)
from app.exceptions.scenario_exceptions import (
    ScenarioAccessDeniedError,
    ScenarioNotFoundError,
)
from app.models.minigame import (
    MinigameCreate,
    MinigameResponse,
    MinigameUpdate,
)
from app.repositories.entity_repo import EntityRepo
from app.repositories.minigame_repo import MinigameRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.services.expression_validation import validate_expression_field_references

REACHABILITY_MAX_ATTEMPTS = 3
REACHABILITY_MIN_WAIT_SECONDS = 1
REACHABILITY_MAX_WAIT_SECONDS = 4
REACHABILITY_REQUEST_TIMEOUT_SECONDS = 5.0

ALLOWED_REPLIT_HOST_SUFFIXES = (".replit.app", ".replit.dev", ".repl.co")


def _validate_safe_replit_url(url: str) -> None:
    """Reject any replit_embed_url that isn't HTTPS to an authorized Replit
    domain — closes an SSRF path where the save-time reachability check's
    outbound GET could otherwise be pointed at internal services or cloud
    metadata endpoints. Host is restricted to suffixes Replit itself
    controls the DNS for, so no live IP resolution is needed (which would
    also block the event loop and require live network access)."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise MinigameValidationError("replit_embed_url must use https")
    host = parsed.hostname
    if not host or not any(
        host.endswith(suffix) for suffix in ALLOWED_REPLIT_HOST_SUFFIXES
    ):
        raise MinigameValidationError(
            "replit_embed_url must point to an authorized replit domain"
        )


_MERGEABLE_FIELDS = (
    "label",
    "minigame_type",
    "trigger_condition_expression",
    "priority",
    "outcome_mode",
    "win_mutation",
    "lose_mutation",
    "tiered_outcomes",
    "timeout_mutation",
    "narrator_instruction_template",
    "dodge_config",
    "replit_embed_url",
)


class MinigameService:
    """Service handling minigame trigger authoring within a master-mode
    scenario."""

    def __init__(
        self,
        minigame_repo: MinigameRepo,
        entity_repo: EntityRepo,
        scenario_repo: ScenarioRepo,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.minigame_repo = minigame_repo
        self.entity_repo = entity_repo
        self.scenario_repo = scenario_repo
        self._http_client = http_client

    async def create_minigame(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID, data: MinigameCreate
    ) -> MinigameResponse:
        """Create a new minigame trigger owned by the given scenario.

        data's minigame_type/outcome_mode shape has already been validated
        by MinigameCreate's own model_validator at request-parse time; this
        method additionally validates the trigger expression's field
        references and, for replit_embed, the URL's live reachability.
        """
        await self._ensure_master_mode_owner_and_validate_expression(
            scenario_id, user_id, data.trigger_condition_expression
        )
        if data.minigame_type == "replit_embed" and data.replit_embed_url:
            await self._check_replit_reachable(data.replit_embed_url)

        minigame = ScenarioMinigame(
            scenario_id=scenario_id,
            label=data.label,
            minigame_type=data.minigame_type,
            trigger_condition_expression=data.trigger_condition_expression,
            priority=data.priority,
            outcome_mode=data.outcome_mode,
            win_mutation=_dump_model(data.win_mutation),
            lose_mutation=_dump_model(data.lose_mutation),
            tiered_outcomes=[t.model_dump(mode="json") for t in data.tiered_outcomes],
            timeout_mutation=_dump_model(data.timeout_mutation),
            narrator_instruction_template=data.narrator_instruction_template,
            dodge_config=_dump_model(data.dodge_config),
            replit_embed_url=data.replit_embed_url,
        )
        created = await self.minigame_repo.create(minigame)
        return MinigameResponse.model_validate(created)

    async def list_minigames(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[MinigameResponse]:
        """List all minigames for a scenario, priority-ordered."""
        await self._ensure_master_mode_owner(scenario_id, user_id)
        items = await self.minigame_repo.list_by_scenario(scenario_id)
        return [MinigameResponse.model_validate(i) for i in items]

    async def get_minigame(
        self, scenario_id: uuid.UUID, minigame_id: uuid.UUID, user_id: uuid.UUID
    ) -> MinigameResponse:
        """Fetch a single minigame, scoped to its owning scenario."""
        await self._ensure_master_mode_owner(scenario_id, user_id)
        minigame = await self._get_scoped(scenario_id, minigame_id)
        return MinigameResponse.model_validate(minigame)

    async def update_minigame(
        self,
        scenario_id: uuid.UUID,
        minigame_id: uuid.UUID,
        user_id: uuid.UUID,
        data: MinigameUpdate,
    ) -> MinigameResponse:
        """Update a minigame's mutable fields, re-validating the merged
        shape since a partial PATCH cannot see the fields it isn't
        touching."""
        await self._ensure_master_mode_owner(scenario_id, user_id)
        minigame = await self._get_scoped(scenario_id, minigame_id)

        update_dict = data.model_dump(exclude_unset=True)
        merged = _merge_for_validation(minigame, update_dict)
        validated = _validate_merged_shape(merged)
        await self._validate_expression(
            scenario_id, validated.trigger_condition_expression
        )
        if validated.minigame_type == "replit_embed" and validated.replit_embed_url:
            await self._check_replit_reachable(validated.replit_embed_url)

        # JSONB columns need plain JSON values. In particular, dodge_config is
        # a nested Pydantic model when supplied by PATCH; preserving its full
        # dump keeps the contract intact across update/snapshot/runtime paths.
        if "dodge_config" in update_dict:
            update_dict["dodge_config"] = _dump_model(update_dict["dodge_config"])
        for field, value in update_dict.items():
            setattr(minigame, field, value)
        updated = await self.minigame_repo.update(minigame)
        return MinigameResponse.model_validate(updated)

    async def delete_minigame(
        self, scenario_id: uuid.UUID, minigame_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Delete a minigame."""
        await self._ensure_master_mode_owner(scenario_id, user_id)
        minigame = await self._get_scoped(scenario_id, minigame_id)
        await self.minigame_repo.delete(minigame)

    async def reorder_minigames(
        self,
        scenario_id: uuid.UUID,
        user_id: uuid.UUID,
        ordered_minigame_ids: list[uuid.UUID],
    ) -> list[MinigameResponse]:
        """Reassign priority (0..N-1) to match the given creator-chosen
        order, mirroring end_conditions' reorder-by-priority pattern."""
        await self._ensure_master_mode_owner(scenario_id, user_id)
        for priority, minigame_id in enumerate(ordered_minigame_ids):
            minigame = await self._get_scoped(scenario_id, minigame_id)
            minigame.priority = priority
            await self.minigame_repo.update(minigame)
        return await self.list_minigames(scenario_id, user_id)

    async def _check_replit_reachable(self, url: str) -> None:
        """Bounded, tenacity-retried HTTP reachability check, riding out a
        sleeping free-tier Repl's cold start (2-3 attempts, exponential
        backoff). A save-time confidence check only — distinct from
        Studio's client-side SDK handshake."""
        _validate_safe_replit_url(url)
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(REACHABILITY_MAX_ATTEMPTS),
                wait=wait_exponential(
                    min=REACHABILITY_MIN_WAIT_SECONDS,
                    max=REACHABILITY_MAX_WAIT_SECONDS,
                ),
            ):
                with attempt:
                    response = await self._http_client.get(
                        url, timeout=REACHABILITY_REQUEST_TIMEOUT_SECONDS
                    )
                    response.raise_for_status()
        except Exception as exc:
            raise MinigameUnreachableError(url=url) from exc

    async def _get_scoped(
        self, scenario_id: uuid.UUID, minigame_id: uuid.UUID
    ) -> ScenarioMinigame:
        """Fetch a minigame, raising 404 if missing or owned by another
        scenario."""
        minigame = await self.minigame_repo.get_by_id(minigame_id)
        if minigame is None or minigame.scenario_id != scenario_id:
            raise MinigameNotFoundError()
        return minigame

    async def _ensure_master_mode_owner_and_validate_expression(
        self,
        scenario_id: uuid.UUID,
        user_id: uuid.UUID,
        trigger_condition_expression: dict[str, object],
    ) -> Scenario:
        """Verify ownership, then validate trigger_condition_expression
        field references."""
        scenario = await self._ensure_master_mode_owner(scenario_id, user_id)
        await self._validate_expression(scenario_id, trigger_condition_expression)
        return scenario

    async def _validate_expression(
        self, scenario_id: uuid.UUID, trigger_condition_expression: dict[str, object]
    ) -> None:
        if not trigger_condition_expression:
            return
        scenario = await self.scenario_repo.get_by_id(scenario_id)
        entities = await self.entity_repo.list_by_scenario(scenario_id)
        entities_by_id = {e.entity_id: e for e in entities}
        validate_expression_field_references(
            trigger_condition_expression,
            scenario.state_schema if scenario else {},
            entities_by_id,
            MinigameValidationError,
        )

    async def _ensure_master_mode_owner(
        self, scenario_id: uuid.UUID, user_id: uuid.UUID
    ) -> Scenario:
        """Verify the scenario exists, is owned by the caller, and is a
        master-mode scenario."""
        scenario = await self.scenario_repo.get_by_id(scenario_id)
        if scenario is None or scenario.status == "archived":
            raise ScenarioNotFoundError()
        if scenario.creator_id != user_id:
            raise ScenarioAccessDeniedError()
        if scenario.mode != "master":
            raise MinigameModeError()
        return scenario


def _dump_model(value: object) -> dict[str, object] | None:
    """Serialize a StateMutation/DodgeConfig Pydantic model instance to a
    plain dict for JSONB storage, passing through None untouched."""
    if value is None:
        return None
    return value.model_dump(mode="json")  # type: ignore[union-attr]


def _merge_for_validation(
    minigame: ScenarioMinigame, update_dict: dict[str, object]
) -> dict[str, object]:
    """Build the full post-update field set (persisted values overridden by
    the incoming partial update) so the merged shape can be validated as a
    whole, exactly as a create request would be."""
    merged: dict[str, object] = {
        field: getattr(minigame, field) for field in _MERGEABLE_FIELDS
    }
    merged.update(update_dict)
    return merged


def _validate_merged_shape(merged: dict[str, object]) -> MinigameCreate:
    """Re-run MinigameCreate's cross-field model_validator against the
    merged post-update shape, translating a Pydantic failure into the
    domain's own MinigameValidationError."""
    try:
        return MinigameCreate(**merged)
    except PydanticValidationError as exc:
        raise MinigameValidationError(str(exc)) from exc
