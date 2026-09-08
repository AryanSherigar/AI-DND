"""Evaluates scenario_minigames triggers against post-turn state.

Runs after the AI tool-call loop's working_state is built, before
state_writer (pipeline.py is the sole sequencer — this file does not call
state_writer or ai_orchestrator itself). Solo-only and master-mode-only,
first-match-wins by priority (scenario_snapshot["scenario_minigames"] is
already priority-ascending, per playthrough_service._snapshot_minigames),
mirroring end_condition_evaluator.py exactly.
"""

import uuid

import structlog
from app.turn.expression_evaluator import evaluate

logger = structlog.get_logger()

EVENT_MINIGAME_TRIGGERED = "minigame_triggered"
EVENT_MINIGAME_EVALUATION_ERROR = "minigame_evaluation_error"
STATE_KEY_PENDING_MINIGAME = "_pending_minigame"


class MatchedMinigameTrigger:
    """Value object for a triggered minigame's play-time payload, not a DB model."""

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload


def evaluate_trigger(
    minigames: list[dict[str, object]],
    final_state: dict[str, object],
    participant_count: int,
    timeout_seconds: int,
) -> MatchedMinigameTrigger | None:
    """Return the first matching minigame's play-time payload, or None.

    A minigame whose trigger expression raises during evaluation is logged
    and treated as "no match this turn" — a malformed expression that
    slipped past Studio validation must never block ordinary play.
    """
    if participant_count > 1 or final_state.get(STATE_KEY_PENDING_MINIGAME):
        return None
    for minigame in minigames:
        if not isinstance(minigame, dict):
            continue
        if _try_evaluate(minigame, final_state):
            payload = _build_payload(minigame, timeout_seconds)
            logger.info(EVENT_MINIGAME_TRIGGERED, minigame_id=payload["minigame_id"])
            return MatchedMinigameTrigger(payload)
    return None


def _try_evaluate(minigame: dict[str, object], final_state: dict[str, object]) -> bool:
    try:
        return evaluate(minigame.get("trigger_condition_expression"), final_state)
    except Exception:
        logger.warning(
            EVENT_MINIGAME_EVALUATION_ERROR,
            minigame_id=minigame.get("minigame_id"),
            exc_info=True,
        )
        return False


def _build_payload(
    minigame: dict[str, object], timeout_seconds: int
) -> dict[str, object]:
    """Only the play-time-safe fields — win_mutation/lose_mutation/
    tiered_outcomes/timeout_mutation/narrator_instruction_template never
    leave the server, per §3.6's "Always" boundary."""
    return {
        "minigame_id": str(minigame["minigame_id"]),
        # This is persisted in _pending_minigame and is therefore stable over
        # a browser reload, while being fresh for every trigger.
        "attempt_id": str(uuid.uuid4()),
        "minigame_type": str(minigame["minigame_type"]),
        "label": str(minigame["label"]),
        "dodge_config": minigame.get("dodge_config"),
        "replit_embed_url": minigame.get("replit_embed_url"),
        "timeout_seconds": timeout_seconds,
    }
