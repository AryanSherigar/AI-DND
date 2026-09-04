# TRS Architecture — Database & Repositories

This document details the persistence layer, mirrored ORM models, and data access repositories in `apps/turn-resolution-service/app/db/` and `app/repositories/`.

---

## 1. Overview & Mirrored Schema Pattern

TRS connects to the same PostgreSQL database as Core API, but maintains an independent, lightweight subset of SQLAlchemy ORM models (`apps/turn-resolution-service/app/db/models/`).
- **No Relationship Overhead**: TRS models omit SQLAlchemy `relationship()` joins and cascading dependency processors, mapping plain Foreign Key columns directly. This guarantees ultra-low turn execution latency.
- **Explicit Commit Control**: Because turn updates occur within an active async SSE generator, repository mutating operations explicitly call `await session.commit()` to guarantee persistence before yielding SSE completion tokens.

---

## 2. Mirrored Models (`app/db/models/`)

- **`playthrough.py` (`Playthrough`)**: Tracks active playthrough session ID, scenario FK, state blob (`state: JSONB`), `turn_count`, `status` (`active`, `completed`, `abandoned`), and end outcome columns (`ended_outcome_tag`, `ended_outcome_title`, `ended_outcome_text`).
- **`scenario.py` (`Scenario`)**: Read-only mirror for authoring instructions, system prompts, opening scenes, rules, and `play_count`.
- **`participant.py` (`Participant`)**: Tracks active players in a session, character IDs, and turn order indices.
- **`turn_log.py` (`TurnLog`)**: Turn history append-only journal (`turn_number`, `user_action`, `narration`, `tool_calls: JSONB`, `state_delta: JSONB`).
- **`share.py` (`Share`)**: Ephemeral and persistent token storage for spectator links.
- **`user.py` (`User`)**: Identity record reference.

---

## 3. Repositories (`app/repositories/`)

### `apps/turn-resolution-service/app/repositories/playthrough_repo.py`
- **Purpose & Layer:** Direct state mutation and lifecycle data access for `Playthrough`.
- **Key Methods:**
  - `get_by_id(playthrough_id) -> Playthrough | None`: Fast single-row fetch.
  - `update_state(playthrough_id, state, turn_count)`: Emits optimized SQL `UPDATE` setting new state and incremented turn counter.
  - `mark_ended(playthrough_id, outcome_tag, outcome_title, outcome_text)`: Sets status to `"completed"` and commits immediately from inside the turn generator.

### `apps/turn-resolution-service/app/repositories/scenario_repo.py`
- **Purpose & Layer:** Read-only scenario access with one single mutation method.
- **Key Methods:**
  - `get_by_id(scenario_id) -> Scenario | None`: Fetches scenario instructions and rules for turn prompt assembly.
  - `increment_play_count(scenario_id) -> None`: Atomic SQL `UPDATE scenarios SET play_count = play_count + 1 WHERE scenario_id = :id`.
- **Architecture Invariant:** TRS never updates any field on `Scenario` other than `play_count` at turn 10.

### `apps/turn-resolution-service/app/repositories/participant_repo.py`
- **Purpose & Layer:** Participant character sheet query repository.
- **Key Methods:**
  - `get_by_id(participant_id)`, `list_by_playthrough(playthrough_id)`, `update_character_state(...)`.

### `apps/turn-resolution-service/app/repositories/turn_log_repo.py`
- **Purpose & Layer:** Turn history insertion and sliding-window retrieval.
- **Key Methods:**
  - `append_turn_log(entry: TurnLog) -> None`: Inserts immutable record of completed turn.
  - `get_recent_turns(playthrough_id, limit=10) -> list[TurnLog]`: Fetches previous turns to inject as conversation history for Gemini.

### `apps/turn-resolution-service/app/repositories/share_repo.py`
- **Purpose & Layer:** Spectator token validation repository.
- **Key Methods:**
  - `get_by_token(share_token) -> Share | None`: Fetches share row and validates expiration and target playthrough.
