"""Evaluates a scenario's end conditions against the just-persisted state.

Runs after state_writer, before memory_writer (pipeline.py is the sole
sequencer — this file does not call state_writer or memory_writer itself).
"""

import structlog

from app.models.turn import LoadedState
from app.turn.expression_evaluator import evaluate

logger = structlog.get_logger()

EVENT_TURN_STEP_COMPLETED = "turn_step_completed"
EVENT_END_CONDITION_MATCHED = "end_condition_matched"
EVENT_END_CONDITION_EVALUATION_ERROR = "end_condition_evaluation_error"
STEP_NAME = "end_condition_evaluator"


class MatchedOutcome:
    """Value object for a triggered end condition's outcome, not a DB model."""

    def __init__(self, outcome_tag: str, outcome_title: str, outcome_text: str) -> None:
        self.outcome_tag = outcome_tag
        self.outcome_title = outcome_title
        self.outcome_text = outcome_text


def evaluate_end_conditions(
    loaded_state: LoadedState, final_state: dict[str, object]
) -> MatchedOutcome | None:
    """Return the first matching end condition's outcome, or None.

    A condition whose expression raises during evaluation is logged and
    treated as "no match this turn" — a malformed expression that slipped
    past Studio validation must never block ordinary play.
    """
    end_conditions = loaded_state.scenario_snapshot.get("end_conditions", [])
    for condition in end_conditions:
        matched = _try_evaluate(condition, final_state)
        if matched:
            logger.info(
                EVENT_END_CONDITION_MATCHED,
                outcome_tag=condition["outcome_tag"],
                outcome_title=condition["outcome_title"],
            )
            return MatchedOutcome(
                outcome_tag=condition["outcome_tag"],
                outcome_title=condition["outcome_title"],
                outcome_text=condition["outcome_text"],
            )
    logger.info(EVENT_TURN_STEP_COMPLETED, step_name=STEP_NAME, matched=False)
    return None


def _try_evaluate(condition: dict[str, object], final_state: dict[str, object]) -> bool:
    try:
        return evaluate(condition.get("condition_expression"), final_state)
    except Exception:
        logger.warning(
            EVENT_END_CONDITION_EVALUATION_ERROR,
            outcome_title=condition.get("outcome_title"),
            exc_info=True,
        )
        return False
