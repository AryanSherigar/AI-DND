"""Evaluates master-mode active conditions before context retrieval/AI orchestration.

Runs after state_loader, before context_retrieval (master mode only) — the
only place besides state_writer that mutates state (Effect C), and it does
so strictly before any Gemini call so the AI narrates against the
post-mutation state (see "The Cairn Presses In" in
docs/specs/master-mode-demo-scenario.md §8).

Every condition whose expression is true this turn contributes its
narrator_instruction (that is what narrator_instruction is for, per the
ScenarioCondition design — always passed to the orchestrator while active);
conditions that also carry a state_mutation (Effect C) additionally apply
and validate it.
"""

from __future__ import annotations

import time

import structlog

from app.models.turn import LoadedState
from app.turn import state_paths
from app.turn.expression_evaluator import evaluate, extract_field_paths
from app.turn.steps import state_validator

logger = structlog.get_logger()

EVENT_TURN_STEP_COMPLETED = "turn_step_completed"
EVENT_EFFECT_C_INVARIANT_VIOLATION = "effect_c_invariant_violation"
STEP_NAME = "condition_evaluator"


class ConditionEvaluationResult:
    """Updated state, narrator instructions to inject, and which field paths
    changed (feeds next turn's field-relevance scoping, via state_writer)."""

    def __init__(
        self,
        state: dict[str, object],
        active_instructions: list[str],
        mutated_paths: set[str],
    ) -> None:
        self.state = state
        self.active_instructions = active_instructions
        self.mutated_paths = mutated_paths


def evaluate_conditions(loaded_state: LoadedState) -> ConditionEvaluationResult:
    """Evaluate this scenario's active conditions against the loaded state."""
    conditions = loaded_state.scenario_snapshot.get("scenario_conditions", []) or []
    last_changed = set(loaded_state.state.get("_last_changed_fields", []) or [])
    prev_active = set(loaded_state.state.get("_active_conditions", []) or [])
    evaluate_all = loaded_state.turn_count == 0 or not last_changed

    start = time.monotonic()
    state = dict(loaded_state.state)
    instructions: list[str] = []
    mutated_paths: set[str] = set()
    currently_active: list[str] = []

    for condition in conditions:
        if not isinstance(condition, dict):
            continue
        cond_id = _condition_id(condition)
        if _should_skip(condition, last_changed, evaluate_all, cond_id in prev_active):
            continue
        if not evaluate(condition.get("condition_expression"), state):
            continue

        _record_active(condition, cond_id, currently_active, instructions)
        state, mutated_paths = _apply_condition_mutation(
            state, condition, loaded_state, mutated_paths
        )

    state["_active_conditions"] = currently_active
    _log_step_completed(start, evaluate_all, len(instructions))
    return ConditionEvaluationResult(state, instructions, mutated_paths)


def _condition_id(condition: dict[str, object]) -> str:
    return str(condition.get("condition_id") or condition.get("label") or "")


def _record_active(
    condition: dict[str, object],
    cond_id: str,
    active_ids: list[str],
    instructions: list[str],
) -> None:
    if cond_id:
        active_ids.append(cond_id)
    instruction = condition.get("narrator_instruction")
    if instruction:
        instructions.append(str(instruction))


def _apply_condition_mutation(
    state: dict[str, object],
    condition: dict[str, object],
    loaded_state: LoadedState,
    mutated_paths: set[str],
) -> tuple[dict[str, object], set[str]]:
    mutation = condition.get("state_mutation")
    if not isinstance(mutation, dict):
        return state, mutated_paths
    new_state, path = _apply_and_validate_effect_c(
        state, mutation, loaded_state, condition
    )
    if path:
        return new_state, mutated_paths | {path}
    return new_state, mutated_paths


def _log_step_completed(start: float, evaluate_all: bool, count: int) -> None:
    logger.info(
        EVENT_TURN_STEP_COMPLETED,
        step_name=STEP_NAME,
        duration_ms=(time.monotonic() - start) * 1000,
        evaluated_all=evaluate_all,
        active_instruction_count=count,
    )


def list_active_condition_labels(
    scenario_conditions: list[object], state: dict[str, object]
) -> list[str]:
    """Every scenario_condition currently true, for the play screen's status-
    badge row. Unlike evaluate_conditions, this checks ALL conditions (not
    just ones whose fields changed this turn) against final post-write state,
    and never applies a state_mutation — read-only."""
    labels: list[str] = []
    for condition in scenario_conditions:
        if not isinstance(condition, dict):
            continue
        if not evaluate(condition.get("condition_expression"), state):
            continue
        label = condition.get("label")
        if label:
            labels.append(str(label))
    return labels


def _should_skip(
    condition: dict[str, object],
    last_changed: set[str],
    evaluate_all: bool,
    was_active: bool,
) -> bool:
    if evaluate_all or was_active:
        return False
    referenced = extract_field_paths(condition.get("condition_expression"))
    return not (referenced & last_changed)


def _apply_and_validate_effect_c(
    state: dict[str, object],
    mutation: dict[str, object],
    loaded_state: LoadedState,
    condition: dict[str, object],
) -> tuple[dict[str, object], str | None]:
    path = str(mutation.get("path") or "")
    if not path:
        return state, None

    candidate_state = state_paths.apply_mutation(
        state, path, str(mutation.get("op", "set")), mutation.get("value")
    )
    result = state_validator.validate_applied_change(
        path, candidate_state, loaded_state.scenario_snapshot
    )
    if not result.is_valid:
        logger.warning(
            EVENT_EFFECT_C_INVARIANT_VIOLATION,
            condition_label=condition.get("label"),
            error=result.error_message,
        )
        return state, None
    return result.updated_state or state, path
