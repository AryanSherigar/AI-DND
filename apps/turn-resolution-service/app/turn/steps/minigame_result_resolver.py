"""Resolves a submitted minigame result into a state mutation + narrator
instruction, exactly like an active condition's Effect C, but triggered by
the incoming request's action_kind instead of an expression.

Runs after state_loader, before context_retrieval (master mode,
action_kind == "minigame_result" only), in the same pipeline slot as
condition_evaluator.py — running first, so condition_evaluator.py's own
Effect C pass sees the minigame's mutation already applied. pipeline.py is
the sole sequencer; this file does not call condition_evaluator or any other
step itself.

Mutation application reuses state_paths.apply_mutation — the same
set/increment/decrement helper condition_evaluator.py's Effect C uses —
rather than reimplementing op-handling a second time.
"""

import structlog

from app.turn import state_paths
from app.turn.steps import state_validator

logger = structlog.get_logger()

EVENT_MINIGAME_RESOLVED = "minigame_resolved"
EVENT_MINIGAME_NOT_FOUND = "minigame_not_found_in_snapshot"
EVENT_MINIGAME_MUTATION_INVALID = "minigame_mutation_invalid"
EVENT_MINIGAME_SCORE_UNRANGED = "minigame_score_unranged"
STATE_KEY_PENDING_MINIGAME = "_pending_minigame"
FALLBACK_INSTRUCTION = "The trial concludes."


class MinigameResolution:
    """Updated state, the narrator instruction to inject into
    active_instructions, and which field path changed (feeds next turn's
    field-relevance scoping, via state_writer) — mirrors condition_evaluator
    .ConditionEvaluationResult's shape."""

    def __init__(
        self,
        state: dict[str, object],
        instruction: str,
        mutated_paths: set[str],
    ) -> None:
        self.state = state
        self.instruction = instruction
        self.mutated_paths = mutated_paths


def resolve_result(
    minigames: list[dict[str, object]],
    state: dict[str, object],
    scenario_snapshot: dict[str, object],
    minigame_id: str,
    outcome_tag: str,
    score: int | None,
) -> MinigameResolution:
    """Apply the matched minigame outcome's mutation and clear
    _pending_minigame — unconditionally, even on a malformed/missing
    mutation, so a playthrough can never get stuck pending."""
    state = dict(state)
    state.pop(STATE_KEY_PENDING_MINIGAME, None)

    minigame = _find_minigame(minigames, minigame_id)
    if minigame is None:
        logger.warning(EVENT_MINIGAME_NOT_FOUND, minigame_id=minigame_id)
        return MinigameResolution(state, FALLBACK_INSTRUCTION, set())

    mutation = _select_mutation(minigame, outcome_tag, score)
    state, mutated_paths, is_mutation_valid = _apply_selected_mutation(
        state, mutation, scenario_snapshot
    )

    instruction = (
        _build_instruction(minigame, outcome_tag, score)
        if is_mutation_valid
        else FALLBACK_INSTRUCTION
    )
    logger.info(
        EVENT_MINIGAME_RESOLVED, minigame_id=minigame_id, outcome_tag=outcome_tag
    )
    return MinigameResolution(state, instruction, mutated_paths)


def _find_minigame(
    minigames: list[dict[str, object]], minigame_id: str
) -> dict[str, object] | None:
    for minigame in minigames:
        if (
            isinstance(minigame, dict)
            and str(minigame.get("minigame_id")) == minigame_id
        ):
            return minigame
    return None


def _select_mutation(
    minigame: dict[str, object], outcome_tag: str, score: int | None
) -> dict[str, object] | None:
    if outcome_tag == "timeout":
        return minigame.get("timeout_mutation")
    if minigame.get("outcome_mode") == "binary":
        key = "win_mutation" if outcome_tag == "win" else "lose_mutation"
        return minigame.get(key)
    return _select_tiered_mutation(minigame, score)


def _select_tiered_mutation(
    minigame: dict[str, object], score: int | None
) -> dict[str, object] | None:
    if score is not None:
        for tier in minigame.get("tiered_outcomes", []) or []:
            if isinstance(tier, dict) and _score_in_tier(tier, score):
                return tier.get("mutation")
    logger.warning(
        EVENT_MINIGAME_SCORE_UNRANGED,
        minigame_id=minigame.get("minigame_id"),
        score=score,
    )
    return None


def _score_in_tier(tier: dict[str, object], score: int) -> bool:
    min_score, max_score = tier.get("min_score"), tier.get("max_score")
    if min_score is None or max_score is None:
        return False
    return float(min_score) <= score <= float(max_score)


def _apply_selected_mutation(
    state: dict[str, object],
    mutation: dict[str, object] | None,
    scenario_snapshot: dict[str, object],
) -> tuple[dict[str, object], set[str], bool]:
    """Apply the matched mutation, if any. Returns (state, mutated_paths,
    is_mutation_valid) — is_mutation_valid is False only when a mutation was
    selected but state_validator rejected it (an invalid state_schema path),
    the one case that falls back to a generic narrator instruction rather
    than the minigame's own template."""
    if not mutation:
        return state, set(), True
    path = str(mutation.get("path") or "")
    if not path:
        return state, set(), True

    candidate_state = state_paths.apply_mutation(
        state, path, str(mutation.get("op", "set")), mutation.get("value")
    )
    result = state_validator.validate_applied_change(
        path, candidate_state, scenario_snapshot
    )
    if not result.is_valid:
        logger.warning(EVENT_MINIGAME_MUTATION_INVALID, error=result.error_message)
        return state, set(), False
    return result.updated_state or state, {path}, True


def _build_instruction(
    minigame: dict[str, object], outcome_tag: str, score: int | None
) -> str:
    template = minigame.get("narrator_instruction_template") or FALLBACK_INSTRUCTION
    return _substitute_tokens(str(template), outcome_tag, score)


def _substitute_tokens(template: str, outcome_tag: str, score: int | None) -> str:
    return template.replace("{outcome_tag}", outcome_tag).replace(
        "{score}", str(score) if score is not None else ""
    )
