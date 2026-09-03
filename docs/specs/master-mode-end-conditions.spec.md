# Spec: Master-Mode End Conditions — Win/Lose/Multi-Outcome Evaluation

## 1. Objective & User Outcome

- **Problem Statement:** `master-mode-data-model.spec.md` gives `end_conditions` a real table with multiple named outcomes per scenario, and `master-mode-turn-pipeline.spec.md` guarantees a validated final state exists after every turn — but nothing evaluates end conditions against that state, and nothing terminates a playthrough or tells the player (or, in multiplayer, everyone else) that it ended. This spec closes that loop.
- **User Story:** As a player, when my actions satisfy one of a scenario's win/lose conditions, I want the playthrough to end with a distinct, named outcome (not just a generic "you win/lose") delivered as part of the same turn's response, so "The Ashen Ending" reads as a deliberate, authored ending rather than a system message.
- **Success Criteria:**
  - After every master-mode turn's state write, all of a scenario's `end_conditions` are evaluated against the final state (via the shared `expression_evaluator` from `master-mode-turn-pipeline.spec.md` — no second implementation).
  - The **first** matching condition (evaluated in a stable, creator-controlled order) wins; a playthrough never matches two endings on the same turn.
  - On a match: `Playthrough.status` becomes `completed`, the matched outcome's `outcome_tag`/`outcome_title`/`outcome_text` are persisted onto the playthrough (not just referenced by ID — the scenario's live `end_conditions` may change after this playthrough ends, and the playthrough must keep exactly the text it actually ended with), and a `playthrough_ended` SSE event is emitted on **both** the per-request turn stream (so the acting player sees it immediately) and the persistent multiplayer notification channel (so other participants see it too).
  - A completed playthrough rejects further `POST /v1/turn` submissions with a clear domain error, not a confusing attempt to keep playing a finished story.
  - Secret endings (`is_secret: true`) are evaluated identically to non-secret ones — secrecy is a Studio/discovery-surface display concern, never a gameplay-logic difference.

## 2. Technical Architecture & Data Flow

- **Components Involved:** a new `turn/steps/end_condition_evaluator.py` pipeline step, `turn/expression_evaluator.py` (reused, defined in `master-mode-turn-pipeline.spec.md`), `PlaythroughRepo`, `notification_manager.py`, `response_streamer.py`.
- **Reference data:** "The Hollow Cairn" (`docs/specs/master-mode-demo-scenario.md`, §9) — three end conditions: "Warden Defeated" (win), "Player Falls" (lose), "The Vigil's Ending" (win, secret).
- **Sequence Flow:**
  1. `state_writer` persists the turn's final validated state (unchanged from `master-mode-turn-pipeline.spec.md`).
  2. **`end_condition_evaluator` (new step, runs immediately after `state_writer`, before `memory_writer`):** iterates `scenario_snapshot.end_conditions` sorted by `priority` ascending (an explicit, creator-controlled integer column — not creation order; see `master-mode-data-model.spec.md`'s `end_conditions.priority` column and `master-mode-studio-ui.spec.md`'s reorder UI), evaluating each `condition_expression` via `expression_evaluator.evaluate()` against the just-written state. Stops at the first match.
  3. On a match: calls `PlaythroughRepo.mark_ended(playthrough_id, outcome_tag, outcome_title, outcome_text)`, which sets `status = 'completed'` and writes the three outcome columns in one update.
  4. `pipeline.py` (already the sole sequencer) checks the evaluator's return value; if an outcome matched, it yields a `playthrough_ended` SSE event on the current response stream *before* the `done` event, and calls `notification_manager.notify_playthrough_ended(playthrough_id, outcome_title)` for every other connected participant.
  5. `request_receiver` (existing step, modified) now rejects a turn submitted against a `Playthrough.status == 'completed'` with `PlaythroughNotActiveError` — this already exists as the check for `'active'` status; extending its message/logging to distinguish "completed" from "abandoned" is the only change needed there.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands

- Test: `pytest tests/turn/steps/test_end_condition_evaluator.py tests/turn/test_pipeline_end_conditions.py -v` (from `apps/turn-resolution-service/`)
- Lint/Format: `ruff format . && ruff check . --fix`

### 3.2. Testing Strategy & Conformance

- **Location:** `apps/turn-resolution-service/tests/turn/steps/test_end_condition_evaluator.py`, plus a pipeline-level integration test.
- **Required cases:**
  - "Warden Defeated" matches when `the_warden.health <= 0`; playthrough status becomes `completed`, outcome fields match the authored text exactly.
  - Ordering: if a turn's state simultaneously satisfies both "Warden Defeated" and "The Vigil's Ending" (both `win`), only the first one in snapshot order is recorded — assert the *other* condition's text never appears on the playthrough.
  - No match: state that satisfies none of the three conditions leaves `status == 'active'` and all three outcome columns `NULL`.
  - Secret ending: "The Vigil's Ending" (`is_secret: true`) is evaluated and matches exactly like a non-secret one — no branch in the evaluator keyed on `is_secret`.
  - Post-completion turn rejection: `POST /v1/turn` against a `completed` playthrough returns the domain error, no pipeline steps beyond `request_receiver` execute (assert via a spy that `state_loader` is never called).
  - SSE ordering: the turn stream emits `narration` chunks, then `state_update` (from the turn-pipeline spec), then `playthrough_ended`, then `done` — in that order, never `done` before `playthrough_ended` on an ending turn.
  - Multiplayer fan-out: in a 2-participant playthrough, the non-acting participant's open `GET /v1/session/{id}/notifications` connection receives `playthrough_ended` within the same request lifecycle (mocked queue assertion, matching `notification_manager.py`'s existing `notify_next_turn` test pattern).

### 3.3. Project Structure & File Layout

**Files to create (new):**
- `apps/turn-resolution-service/app/turn/steps/end_condition_evaluator.py`
- `apps/turn-resolution-service/tests/turn/steps/test_end_condition_evaluator.py`

**Files to modify:**
- `apps/turn-resolution-service/app/turn/pipeline.py` — insert the evaluator step after `state_writer`, before `memory_writer`; branch on its result to emit `playthrough_ended` and skip/continue to `memory_writer` regardless (memory batching still runs on the ending turn — no reason to skip it).
- `apps/turn-resolution-service/app/turn/steps/response_streamer.py` — add `playthrough_ended_event(outcome_tag: str, outcome_title: str, outcome_text: str) -> ServerSentEvent`, following the existing `narration_event`/`done_event` pattern exactly (pure formatting, no side effects).
- `apps/turn-resolution-service/app/session/notification_manager.py` — add `notify_playthrough_ended(playthrough_id: uuid.UUID, outcome_title: str) -> None`, mirroring `notify_next_turn`'s existing shape (push to every subscribed participant for this `playthrough_id`, not just one — this is the one notification that's genuinely broadcast, unlike `your_turn`).
- `apps/turn-resolution-service/app/repositories/playthrough_repo.py` — add `mark_ended(playthrough_id, outcome_tag, outcome_title, outcome_text) -> None`.
- `apps/turn-resolution-service/app/turn/steps/request_receiver.py` — extend the existing active-status check's error message to distinguish "this playthrough already ended" from other non-active states.
- `apps/core-api/app/db/migrations/versions/004_playthrough_end_outcome.py` (new migration) — add `ended_outcome_tag` (`String(10)`, nullable, same `win`/`lose` check constraint as `end_conditions.outcome_tag`), `ended_outcome_title` (`String(255)`, nullable), `ended_outcome_text` (`Text`, nullable), and `is_playtest` (`Boolean`, `server_default="false"`, not null) to `playthroughs`. `is_playtest` is consumed by `master-mode-studio-ui.spec.md`'s playtest-mode feature: a playtest playthrough is created and played through the normal turn pipeline unmodified, but is excluded from `Scenario.play_count` increments (`state_writer.py`'s existing turn-10 increment check gains an `if not loaded_state.is_playtest` guard) and from any public/discovery playthrough listing (Core API's existing `list_public_playthroughs`, unchanged endpoint, adds a `WHERE NOT is_playtest` filter).
- `apps/core-api/app/db/models/playthrough.py` and `apps/turn-resolution-service/app/db/models/playthrough.py` — add the four new columns (both services have their own SQLAlchemy model of the shared table per the existing "shared schema, no migrations" split noted in the repo's file structure).
- `apps/turn-resolution-service/app/models/turn.py` — add `is_playtest: bool` to `LoadedState`, sourced from `Playthrough.is_playtest` in `state_loader.py`.
- `apps/core-api/app/services/playthrough_service.py` — ensure `scenario_snapshot.end_conditions` is written sorted by the new `priority` column (ascending) so `end_condition_evaluator`'s "first match wins" rule reflects the creator's explicit ordering from the Studio, not incidental creation order.

### 3.4. Code Style & Interfaces

```python
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
    """Return the first matching end condition's outcome, or None."""
    end_conditions = loaded_state.scenario_snapshot.get("end_conditions", [])
    for condition in end_conditions:
        if evaluate(condition["condition_expression"], final_state):
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
```

Why a plain value object (`MatchedOutcome`) instead of the `EndCondition` Pydantic model from the data-model spec: this function operates only on the frozen `scenario_snapshot` copy (a `dict`, per ADR-8 — TRS never touches the live `end_conditions` table), so re-using the Core-API-side Pydantic model here would be a cross-service import that doesn't exist in this monorepo's dependency graph; a small local type is the honest shape instead.

### 3.5. Git & Review Workflow

- Branch: `feat/master-mode-end-conditions`
- Depends on `master-mode-data-model.spec.md` (needs the `end_conditions` table and its snapshot inclusion) and `master-mode-turn-pipeline.spec.md` (needs `expression_evaluator.py` and a validated final state to evaluate against) merged first.
- Commit scope: one commit for the migration + repo/model column additions, one for `end_condition_evaluator.py` + pipeline wiring, one for the SSE event + notification broadcast.
- PR checklist: an ending turn's SSE event order is asserted in an integration test, not just unit-tested per step; multiplayer fan-out is tested with at least 2 participants.

### 3.6. Boundaries (Three-Tier Model)

- ✅ **Always:** evaluate all end conditions in deterministic snapshot order; persist the *matched outcome's actual text*, not a pointer to a row that could change later; run this step for every master-mode turn, not just ones where an obvious win/lose flag changed.
- ⚠️ **Ask First:** changing "first match wins" to any other precedence rule (e.g. "most specific match wins") — that's a real semantic change a creator would need to understand, not a pure implementation detail.
- 🚫 **Never:** let a completed playthrough accept another turn; let `end_condition_evaluator` itself mutate `Playthrough.state` (it only reads state and writes completion metadata — any state mutation belongs to `condition_evaluator`/Effect C, a different step with a different job).

## 4. Edge Cases, Rate Limits & Graceful Degradation

- **No end conditions authored:** a master-mode scenario with an empty `end_conditions` list is valid (not every scenario needs a formal ending) — `evaluate_end_conditions` returns `None` immediately, zero overhead, no error.
- **Both `win` and `lose` conditions match the same state:** resolved by the same "first in snapshot order" rule as a same-tag collision — order is the single source of truth for precedence, not tag semantics. This should be flagged as a real-time Studio validation warning (creator likely made an authoring mistake) per `master-mode-studio-ui.spec.md`, but is not itself an error at evaluation time.
- **Multiplayer participant disconnected when `playthrough_ended` fires:** identical graceful-degradation posture as the existing `your_turn` notification — a no-op if the participant has no open connection; their client discovers the ended status on next `GET /v1/playthroughs/{id}` poll (Core API, unchanged by this spec).
- **`end_condition_evaluator` itself throwing (malformed expression that slipped past Studio validation):** caught and logged as `EVENT_END_CONDITION_EVALUATION_ERROR`, treated as "no match this turn" rather than failing the whole turn — a broken end condition must never block ordinary play; it just never fires until a creator fixes it.

## 5. Phased Implementation Tasks (Task Checklist)

- [ ] **Task 1 (Schema):** Write `004_playthrough_end_outcome.py` migration; add the three columns to both services' `Playthrough` ORM models. Verify: `alembic upgrade head && alembic downgrade -1`.
- [ ] **Task 2 (Evaluator):** Implement `end_condition_evaluator.py`. Verify: `pytest tests/turn/steps/test_end_condition_evaluator.py`.
- [ ] **Task 3 (Persistence + rejection):** Add `PlaythroughRepo.mark_ended`; extend `request_receiver.py`'s active-status check. Verify: repo-level test + a rejected-turn integration test.
- [ ] **Task 4 (Streaming + notification):** Add `playthrough_ended_event` to `response_streamer.py`; add `notify_playthrough_ended` to `notification_manager.py`; wire both into `pipeline.py` in correct SSE order. Verify: `pytest tests/turn/test_pipeline_end_conditions.py` asserting event order and multiplayer fan-out.
- [ ] **Task 5 (Snapshot ordering):** Ensure Core API's `playthrough_service.py` writes `scenario_snapshot.end_conditions` sorted by `priority` ascending. Verify: a snapshot fixture test confirms order matches `priority` for a 3-condition scenario with non-default priorities.
