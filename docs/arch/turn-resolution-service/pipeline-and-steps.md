# TRS Architecture — Turn Pipeline & Steps

This document details the turn resolution pipeline orchestrator (`pipeline.py`) and all 12 decoupled pipeline steps located in `apps/turn-resolution-service/app/turn/steps/`.

---

## 1. Pipeline Execution Lifecycle

The turn pipeline executes per-action gameplay loops. It supports two modes:
- **Newbie Mode**: Freeform narrative action without structured tool calling or state schema enforcement.
- **Master Mode**: Enforces dynamic condition evaluation, AI tool calling, schema validation, map state synchronization, end condition checks, and memory ingestion.

```mermaid
sequenceDiagram
    autonumber
    participant Pipeline as pipeline.py
    participant Loader as state_loader
    participant Cond as condition_evaluator
    participant Context as context_retrieval
    participant AI as ai_orchestrator
    participant Tool as tool_handler
    participant Valid as state_validator
    participant Map as map_state_sync
    participant Writer as state_writer
    participant End as end_condition_evaluator
    participant Mem as memory_writer
    participant Stream as response_streamer

    Pipeline->>Loader: 1. Load DB state (playthrough, scenario, participants)
    opt Master Mode
        Pipeline->>Cond: 2. Evaluate active conditions & apply Effect C
    end
    Pipeline->>Context: 3. Query relevant facts from Memory Layer
    Pipeline->>AI: 4. Invoke Gemini streaming with tool definitions
    loop Token Streaming & Tool Calls
        AI-->>Stream: Stream narration chunks immediately to client
        AI-->>Tool: 5. Dispatch tool calls (update_state, update_entity)
    end
    opt Master Mode
        Pipeline->>Valid: 6. Validate mutations against Rule Invariants
        Pipeline->>Map: 7. Sync location changes to map pin discovery
    end
    Pipeline->>Writer: 8. Persist updated state & append turn log to Cloud SQL
    opt Master Mode
        Pipeline->>End: 9. Check win/loss conditions
    end
    Pipeline->>Mem: 10. Write newly established world facts to Memory Layer
    Pipeline->>Stream: 11. Yield final [DONE] SSE event & close stream
```

---

## 2. Pipeline Orchestrator Profile

### `apps/turn-resolution-service/app/turn/pipeline.py`
- **Purpose & Layer:** Central coordinator of turn execution.
- **Key Exports & Functions:**
  - `run_turn(request_input: TurnRequestInput, session: AsyncSession) -> EventSourceResponse`: Main entrypoint. Sequences all steps and yields `ServerSentEvent` objects.
  - Handles fallback narration errors gracefully; yields degraded write messages (`_DEGRADED_WRITE_MESSAGE`) if state persistence encounters a transient error.
  - Broadcasts turn completion to active spectators via `spectator_manager` and triggers player alerts via `notification_manager`.
- **Dependencies & Interactions:** Imports steps from `app/turn/steps/`. Injects DB repositories.
- **Architecture Rules & Invariants:**
  - The **only** file permitted to import or sequence multiple steps.
  - Never buffers SSE narration tokens in memory before yielding.

---

## 3. The 12 Pipeline Step Profiles

### 1. `apps/turn-resolution-service/app/turn/steps/request_receiver.py`
- **Purpose & Layer:** Input ingestion, validation, and sanitization.
- **Key Functions:** `receive_turn_request(request_input: TurnRequestInput) -> TurnRequest`.
- **Logic:** Validates payload boundaries, trims whitespace, verifies player character ID, and rejects blank actions or malformed turn payloads.

### 2. `apps/turn-resolution-service/app/turn/steps/state_loader.py`
- **Purpose & Layer:** Parallel entity and game state retrieval.
- **Key Functions:** `load_state(turn_request: TurnRequest, repos...) -> LoadedState`.
- **Logic:** Concurrently loads the active `Playthrough`, owning `Scenario`, all `Participant` records, and the sliding window of previous `TurnLog` entries (configured by `turn_history_window_size`).

### 3. `apps/turn-resolution-service/app/turn/steps/condition_evaluator.py`
- **Purpose & Layer:** Master Mode dynamic condition trigger evaluation.
- **Key Functions:** `evaluate_conditions(loaded_state: LoadedState) -> ConditionEvaluationResult`.
- **Logic:** Evaluates scenario condition expressions against current `game_state`. Active conditions inject temporary system prompt instructions (Effect C) into the AI orchestrator before narration begins.

### 4. `apps/turn-resolution-service/app/turn/steps/context_retrieval.py`
- **Purpose & Layer:** Semantic memory and world lore retrieval.
- **Key Functions:** `retrieve_context(turn_request, loaded_state) -> RetrievedContext`.
- **Logic:** Calls `memory_client.query_memory()` with the player's action and historical context, retrieving relevant knowledge facts to inject into Gemini's context window.

### 5. `apps/turn-resolution-service/app/turn/steps/ai_orchestrator.py`
- **Purpose & Layer:** Vertex AI Gemini prompt assembly, tool declaration, and streaming execution.
- **Key Functions:** `stream_turn_resolution(...) -> AsyncIterator[TurnStreamChunk]`.
- **Logic:** Assembles system instructions, persona modifiers, character stats, condition instructions, and memory facts. Declares tools (`update_game_state`, `update_entity_state`, `trigger_event`). Emits tokens live while buffering tool calls for execution.

### 6. `apps/turn-resolution-service/app/turn/steps/tool_handler.py`
- **Purpose & Layer:** AI tool call execution and state patch compilation.
- **Key Functions:** `execute_tool_calls(tool_calls, current_state) -> ToolExecutionResult`.
- **Logic:** Validates arguments against schema bounds, applies JSON patches to player attributes or entity records, and captures structured tool execution logs.

### 7. `apps/turn-resolution-service/app/turn/steps/state_validator.py`
- **Purpose & Layer:** Invariant enforcement and state boundary validation.
- **Key Functions:** `validate_state(candidate_state, rule_invariants) -> ValidationResult`.
- **Logic:** Runs AST expression checks for all scenario rule invariants (e.g. `hp >= 0`). If an invariant fails, rolls back the candidate state mutation while preserving narration.

### 8. `apps/turn-resolution-service/app/turn/steps/map_state_sync.py`
- **Purpose & Layer:** Spatial location tracking and map pin discovery.
- **Key Functions:** `sync_map_state(candidate_state, scenario_maps) -> MapSyncResult`.
- **Logic:** Detects when `current_location_id` changes; automatically updates discovered pins and reveals connected map regions in `candidate_state`.

### 9. `apps/turn-resolution-service/app/turn/steps/state_writer.py`
- **Purpose & Layer:** Durable persistence to PostgreSQL.
- **Key Functions:** `write_state(session, candidate_state, turn_log_entry) -> None`.
- **Logic:** Writes updated `current_state` and increments `current_turn` on `Playthrough`. Appends an immutable `TurnLog` row. Increments `Scenario.play_count` if turn equals threshold (turn 10).

### 10. `apps/turn-resolution-service/app/turn/steps/end_condition_evaluator.py`
- **Purpose & Layer:** Win/loss outcome evaluation.
- **Key Functions:** `check_end_conditions(state, end_conditions) -> MatchedOutcome | None`.
- **Logic:** Checks boolean end condition expressions. If met, marks playthrough status as `"ended"` and sets `end_outcome` (`victory`, `defeat`, `neutral`).

### 11. `apps/turn-resolution-service/app/turn/steps/memory_writer.py`
- **Purpose & Layer:** Long-term memory synchronization.
- **Key Functions:** `persist_turn_memory(playthrough_id, turn_number, action, narration) -> None`.
- **Logic:** Sends newly established narrative facts and state updates to `memory_client.ingest_memory()` for graph storage.

### 12. `apps/turn-resolution-service/app/turn/steps/response_streamer.py`
- **Purpose & Layer:** SSE event formatting and stream termination.
- **Key Functions:** `format_sse_event(event_type, data) -> ServerSentEvent`.
- **Logic:** Encodes narration tokens, state updates, map discoveries, and the final `[DONE]` event into SSE protocol format.
