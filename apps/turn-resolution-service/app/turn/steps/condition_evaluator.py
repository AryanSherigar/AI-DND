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
    evaluate_all = loaded_state.turn_count == 0 or not last_changed

    start = time.monotonic()
    state = loaded_state.state
    active_instructions: list[str] = []
    mutated_paths: set[str] = set()

    for condition in conditions:
        if not isinstance(condition, dict):
            continue
        if _should_skip(condition, last_changed, evaluate_all):
            continue
        if not evaluate(condition.get("condition_expression"), state):
            continue

        instruction = condition.get("narrator_instruction")
        if instruction:
            active_instructions.append(str(instruction))

        mutation = condition.get("state_mutation")
        if mutation:
            state, path = _apply_and_validate_effect_c(
                state, mutation, loaded_state, condition
            )
            if path:
                mutated_paths.add(path)

    logger.info(
        EVENT_TURN_STEP_COMPLETED,
        step_name=STEP_NAME,
        duration_ms=(time.monotonic() - start) * 1000,
        evaluated_all=evaluate_all,
        active_instruction_count=len(active_instructions),
    )
    return ConditionEvaluationResult(state, active_instructions, mutated_paths)


def _should_skip(
    condition: dict[str, object], last_changed: set[str], evaluate_all: bool
) -> bool:
    if evaluate_all:
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

    candidate_state = _apply_effect_c_mutation(state, mutation, path)
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


def _apply_effect_c_mutation(
    state: dict[str, object], mutation: dict[str, object], path: str
) -> dict[str, object]:
    op = mutation.get("op", "set")
    value = mutation.get("value")

    if op == "set":
        new_value = value
    elif op in ("increment", "decrement"):
        current = state_paths.get_field_value(state, path) or 0
        delta = float(value or 0)
        new_value = (
            float(current) + delta if op == "increment" else float(current) - delta
        )
    else:
        return state

    return state_paths.set_field_value(state, path, new_value)
