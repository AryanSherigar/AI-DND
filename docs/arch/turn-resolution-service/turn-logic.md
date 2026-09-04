# TRS Architecture — Turn Logic & Domain Evaluators

This document details the pure business logic modules located in `apps/turn-resolution-service/app/turn/`. These components handle AST expression parsing, dynamic audio mood classification, turn rotation sequencing, tool schemas, and state path lookups.

---

## 1. Overview

Turn logic modules are stateless, deterministic evaluation engines that operate with zero direct database or network I/O. They provide shared primitives consumed by the pipeline steps.

---

## 2. File Profiles

### `apps/turn-resolution-service/app/turn/expression_evaluator.py`
- **Purpose & Layer:** Grammar interpreter and AST evaluator for dynamic condition triggers and rule invariants.
- **Key Exports & Functions:**
  - `evaluate(expression: dict[str, object] | None, state: dict[str, object]) -> bool`: Evaluates a nested expression tree against the current game state.
  - `extract_field_paths(expression) -> set[str]`: Extracts all dot-notation field paths referenced in an expression tree (used for selective re-evaluation).
  - Supported operators: `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `contains`, `matches`.
  - Logical connectives: `AND`, `OR`, `NOT`.
- **Dependencies & Interactions:** Consumed by `condition_evaluator.py` and `state_validator.py`.
- **Architecture Rules & Invariants:**
  - Zero use of Python's dangerous `eval()` or `exec()`.
  - Strict type casting via `_safe_num` to prevent runtime crashes during numeric comparisons against mismatched types.

### `apps/turn-resolution-service/app/turn/mood.py`
- **Purpose & Layer:** Dynamic narrative mood tag parser and audio soundtrack classifier.
- **Key Exports & Functions:**
  - `MoodTag(StrEnum)`: The 5 canonical soundtrack moods: `PEACEFUL`, `MYSTERY`, `TENSION`, `COMBAT`, `MELANCHOLY`.
  - `MOOD_SYNONYMS`: Dictionary mapping over 20 colloquial adjectives (`ominous`, `dread`, `battle`, `serene`, `grief`) to canonical tags.
  - `normalize_mood(raw_text: str) -> MoodTag`: Strips bracket syntax and resolves synonyms to canonical enum tags.
  - `extract_mood_from_stream(token: str, buffer: str) -> tuple[MoodTag | None, str]`: Extracts leading mood markers (e.g. `[mood: tension]`) from the initial AI narration stream chunk, stripping the bracketed directive from player-visible output.
- **Dependencies & Interactions:** Consumed by `ai_orchestrator.py` and `response_streamer.py`.
- **Architecture Rules & Invariants:** Caps mood inspection buffer at `MAX_MOOD_BUFFER_LENGTH = 60` to ensure prompt tokens are not held back indefinitely if no mood tag is emitted.

### `apps/turn-resolution-service/app/turn/turn_order.py`
- **Purpose & Layer:** Multi-participant turn sequencing and validation.
- **Key Exports & Functions:**
  - `expected_participant(participants: list[Participant], current_turn: int) -> Participant`: Computes whose turn it is using round-robin modulo arithmetic over active participants.
  - `validate_participant_turn(user_id, participants, current_turn)`: Enforces turn discipline in multiplayer sessions, rejecting actions submitted out of turn.
- **Dependencies & Interactions:** Consumed by `pipeline.py`.

### `apps/turn-resolution-service/app/turn/tool_definitions.py`
- **Purpose & Layer:** Gemini FunctionDeclaration declarations for Master Mode AI tool calling.
- **Key Exports & Functions:**
  - `get_tool_declarations(scenario) -> list[dict]`: Constructs OpenAPI/Gemini function schemas:
    - `update_game_state(path, value)`: Updates variables in `current_state`.
    - `update_entity_state(entity_id, attribute, value)`: Modifies dynamic NPC/item properties.
    - `trigger_event(event_name, payload)`: Emits non-persistent narrative cues.
- **Dependencies & Interactions:** Consumed by `ai_orchestrator.py`.

### `apps/turn-resolution-service/app/turn/state_paths.py`
- **Purpose & Layer:** JSONPath and dot-notation dictionary navigation utility.
- **Key Exports & Functions:**
  - `get_path_value(state: dict, path: str) -> object`: Safely traverses nested dictionary paths (e.g. `"player.inventory.gold"`).
  - `set_path_value(state: dict, path: str, value: object) -> None`: In-place nested dictionary mutation.
- **Dependencies & Interactions:** Consumed by `tool_handler.py` and `expression_evaluator.py`.
