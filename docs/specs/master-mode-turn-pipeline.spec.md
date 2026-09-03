# Spec: Master-Mode Turn Pipeline — Tool-Calling, State Validation, Conditions

## 1. Objective & User Outcome

- **Problem Statement:** The turn pipeline (`apps/turn-resolution-service`) works end-to-end for newbie mode, but every master-mode file it needs is a 0-byte stub (`models/game_state.py`, `models/tool_call.py`, `turn/steps/condition_evaluator.py`, `turn/steps/state_validator.py`, `turn/steps/tool_handler.py`), and `pipeline.py`'s own docstring says so explicitly. `ai_orchestrator.py` only streams plain narration today — it has no concept of tool calls at all. This spec makes master-mode playthroughs actually playable: typed, validated, tool-mutable game state; active conditions and Effect C; and mechanically-enforced world-rule invariants — all under a real latency budget.
- **User Story:** As a player in a master-mode playthrough, I want my actions to meaningfully and reliably change tracked game state (my health, an NPC's awareness, my inventory) through an AI narrator that can't violate the world's own rules, without waiting unreasonably long for a response.
- **Success Criteria:**
  - `POST /v1/turn` on a master-mode playthrough drives Gemini with native function-calling using the fixed generic tool set; every accepted mutation is Pydantic-validated against a model built from the playthrough's `state_schema` + entity `attributes_schema` before it touches `Playthrough.state`.
  - A rejected tool call (schema violation or invariant violation) is returned to Gemini as a function-call failure within the same generation — no extra HTTP round-trip, matching ADR-4.
  - Active conditions fire every turn; Effect C conditions apply their `state_mutation` **before** the Gemini call (§2 of `master-mode-demo-scenario.md`, "The Cairn Presses In").
  - Hidden facts never reach the narration prompt unless the playthrough's `revealed_facts` list includes them.
  - A turn with 0–2 tool calls completes (dispatches the `done` event) in ~5s p95; a turn that hits the 5-round-trip tool-call cap is allowed up to ~10s and still finalizes gracefully rather than hanging.
  - Condition/invariant evaluation stays under 100ms per turn by only re-evaluating expressions whose referenced fields actually changed this turn.
  - The validation Pydantic model is built once per playthrough and reused across turns wherever the serving instance is warm — not unconditionally rebuilt every turn.
  - Zero `ruff` warnings; `pipeline.py` remains the only file that knows step order; `gemini_client.py` remains the only file that calls Vertex AI; `ai_orchestrator.py` remains the only file permitted to call `gemini_client.py`.

## 2. Technical Architecture & Data Flow

- **Components Involved:** FastAPI (`turn.py` router, unchanged), the turn pipeline's `steps/` package, `google-genai` SDK (native function-calling), Pydantic v2 dynamic model construction, the (still-mocked) memory client.
- **Reference data:** all examples below are "The Hollow Cairn" from `docs/specs/master-mode-demo-scenario.md`.
- **Upstream dependency on Core API:** `Playthrough.scenario_snapshot` (written once, at playthrough creation, by Core API's `playthrough_service.py` per ADR-8) must now also include each entity's `attributes_schema`/`obtainable`/`narrator_instruction`, the scenario's `rule_invariants`, and `scenario_conditions` rows including their new `state_mutation` column — TRS never reads `Scenario` or its sub-resource tables directly during a turn. This spec treats that snapshot shape as a precondition; the actual write happens in `apps/core-api/app/services/playthrough_service.py` (listed under Files to Modify, §3.3, since it's the one non-TRS file this spec depends on).

- **Sequence Flow — one master-mode turn:**
  1. `request_receiver` / `state_loader` run unchanged.
  2. **`condition_evaluator` (new step, runs after `state_loader`, before `context_retrieval`):** loads `scenario_snapshot.scenario_conditions` and `scenario_snapshot.rule_invariants`; for each condition whose expression references a field that changed on the *previous* turn (or all of them, on turn 1), evaluates it against `loaded_state.state`. Conditions with a `state_mutation` (Effect C) and a now-true expression apply that mutation directly to `loaded_state.state` — this is the only place besides `state_writer` that changes state, and it runs strictly before `context_retrieval`/`ai_orchestrator` so the AI narrates against the post-mutation state. Conditions without a mutation (narrator-instruction-only) are collected into an `active_instructions: list[str]` carried forward to `ai_orchestrator`.
  3. `context_retrieval` runs as today, but now also forwards `loaded_state.state.get("revealed_facts", [])` as part of `game_state` in `MemoryQueryRequest` (already a `dict[str, Any]`, no contract change needed), and **filters `hidden` facts not present in `revealed_facts` out of the response before it's used** (§3.4).
  4. **`ai_orchestrator` (extended):** builds the system instruction from `narrator_persona` (checkpoint-overridden per §2.10 of the demo scenario), the active conditions' `narrator_instruction` text, any on-scene entities' `narrator_instruction` (§3.4 heuristic), and — for master mode — the fixed tool declarations (`tool_definitions.py`, new file) plus each `rule_invariants.narrator_text`. Calls `gemini_client` with tools enabled. When Gemini emits a function call, hands the call to `tool_handler.prepare_mutation()`, then to `state_validator.validate()`; on success, applies the mutation to an in-memory working copy of state and sends a success function-response back into the same Gemini call; on failure, sends a failure function-response with the rejection reason. Repeats until Gemini stops calling tools, a natural stop, or the 5-round-trip cap is hit (§4).
  5. `state_writer` persists the final validated state (as today), plus runs end-condition evaluation (delegated to `master-mode-end-conditions.spec.md` — this spec only guarantees the final validated state is available for that check).
  6. `memory_writer`, `response_streamer` run unchanged.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands

- Build check: `python3 -c "import fastapi, pydantic, google.genai"` (from `apps/turn-resolution-service/`)
- Test: `pytest tests/turn/steps/test_condition_evaluator.py tests/turn/steps/test_state_validator.py tests/turn/steps/test_tool_handler.py tests/turn/steps/test_ai_orchestrator.py tests/models/test_game_state.py -v`
- Lint/Format: `ruff format . && ruff check . --fix`

### 3.2. Testing Strategy & Conformance

- **Location:** `apps/turn-resolution-service/tests/turn/steps/`, mirroring source, per CLAUDE.md.
- **Mocking:** external network calls (Gemini, memory layer) mocked via `httpx`/SDK-level mocks per CLAUDE.md — never mock the database.
- **Required cases:**
  - `state_validator` rejects a mutation with a wrong type (e.g. `player.health = "high"`), an out-of-range value (e.g. `player.health = 500` against `max: 100`), and a violated invariant (e.g. a mutation that would set `player.health = 120` while `max_health = 100` — even if the raw type/range check on `health` alone would pass, the cross-field invariant from §7 of the demo scenario must still catch it).
  - `state_validator` accepts a valid mutation and returns the merged state.
  - `condition_evaluator`: "The Cairn Presses In" (Effect C) fires and decrements `player.sanity` by 2 when `flags.entered_cairn == true`, and does **not** fire when false. Runs before any Gemini call is issued (assert via mock call-order, not just final state).
  - `condition_evaluator`: only re-evaluates conditions whose referenced fields changed on the prior turn — assert via a spy/counter that an unrelated condition (referencing a field untouched this turn) is skipped.
  - `ai_orchestrator` tool-call loop: a 2-round-trip sequence (`roll_dice` then `set_field`, per §12 of the demo scenario) completes and both calls' results reach `TurnLog.tool_calls`.
  - `ai_orchestrator` cap: a mock Gemini that keeps calling tools past 5 round-trips is force-finalized on the 6th attempt — no hang, `done` event still emitted, and the finalization is logged (`EVENT_TOOL_CALL_CAP_HIT`).
  - Hidden fact filtering: a `context_retrieval` response containing one `hidden: true` fact and one `hidden: false` fact, with `revealed_facts: []`, yields only the non-hidden fact to `ai_orchestrator`'s prompt builder.
  - `models/game_state.py` model-builder: constructing a model from the demo scenario's `state_schema` accepts a valid state dict and rejects one with a bad nested-field type; the LRU cache returns the identical model instance on a second call with the same scenario snapshot hash, and a different instance after a hash change.
  - Latency (non-blocking, informational only — not a hard CI gate): a benchmark test asserts `condition_evaluator` completes in well under 100ms against a scenario with ~20 conditions/invariants.

### 3.3. Project Structure & File Layout

**Files to fill in (currently 0-byte stubs):**
- `apps/turn-resolution-service/app/models/game_state.py`
- `apps/turn-resolution-service/app/models/tool_call.py`
- `apps/turn-resolution-service/app/turn/steps/condition_evaluator.py`
- `apps/turn-resolution-service/app/turn/steps/state_validator.py`
- `apps/turn-resolution-service/app/turn/steps/tool_handler.py`

**Files to create (new):**
- `apps/turn-resolution-service/app/turn/expression_evaluator.py` — the single shared implementation of the condition-expression grammar (comparison `==`/`!=`/`<`/`<=`/`>`/`>=`, boolean composition `AND`/`OR`/`NOT` nesting, set membership `in`/`contains`, string match), operating on a `dict[str, object]` state tree and a field-path string (e.g. `"player.health"`, `"the_warden.awareness"`). This is the one evaluator used by `condition_evaluator.py` (active conditions + Effect C), `state_validator.py` (rule invariants), **and** `master-mode-end-conditions.spec.md`'s end-condition evaluation step — do not let a second implementation grow in that later spec; it must import this module.
- `apps/turn-resolution-service/app/turn/tool_definitions.py` — static fixed tool schema list + discipline-bearing descriptions.
- `apps/turn-resolution-service/app/exceptions/validation_exceptions.py` (the file already exists per the README's proposed layout but is currently empty — verify and fill).
- `apps/turn-resolution-service/tests/turn/test_expression_evaluator.py`, `apps/turn-resolution-service/tests/models/test_game_state.py`, plus one test file per filled step.

**Files to modify:**
- `apps/turn-resolution-service/app/turn/pipeline.py` — insert `condition_evaluator` between `state_loader` and `context_retrieval`, conditional on `loaded_state.scenario_snapshot.get("mode") == "master"`; update the module docstring (it currently says these steps are "intentionally not wired in yet").
- `apps/turn-resolution-service/app/turn/steps/ai_orchestrator.py` — add the tool-calling loop; `generate_narration` becomes mode-aware (master mode uses the loop, newbie mode keeps today's plain streaming path unchanged).
- `apps/turn-resolution-service/app/integrations/gemini_client.py` — add a `generate_with_tools(...)` function alongside the existing `stream_narration(...)`; both remain the only functions any other file calls into Vertex AI through.
- `apps/turn-resolution-service/app/config.py` — add `tool_call_max_round_trips: int = 5`.
- `apps/turn-resolution-service/app/models/memory.py` — add `hidden: bool = False` to `Fact`.
- `apps/turn-resolution-service/app/turn/steps/context_retrieval.py` — add hidden-fact filtering (§3.4).
- `apps/turn-resolution-service/app/turn/steps/state_writer.py` — accept and persist the (possibly Effect-C-mutated) state from `condition_evaluator`, not just the AI-produced state, and persist `updated_state["revealed_facts"]` if `condition_evaluator` changed it.
- `apps/core-api/app/services/playthrough_service.py` — extend `scenario_snapshot` construction to include entity `attributes_schema`/`obtainable`/`narrator_instruction`, `rule_invariants`, and `scenario_conditions.state_mutation` (depends on `master-mode-data-model.spec.md` being complete first).

### 3.4. Code Style & Interfaces

#### Dynamic model construction (`app/models/game_state.py`):

```python
from __future__ import annotations

import hashlib
import json
from functools import lru_cache

from pydantic import BaseModel, create_model

_TYPE_MAP: dict[str, type] = {"string": str, "number": float, "boolean": bool}

def _schema_hash(state_schema: dict[str, object], entity_attrs: dict[str, object]) -> str:
    """Stable cache key for a scenario_snapshot's validation shape."""
    payload = json.dumps({"state": state_schema, "entities": entity_attrs}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()

@lru_cache(maxsize=128)
def _build_model(schema_hash: str, schema_json: str) -> type[BaseModel]:
    """Build once per distinct schema shape; cached for the life of the worker process.

    Cloud Run scale-to-zero means this cache is best-effort, not a durable
    guarantee — a cold start rebuilds it once, cheaply (this is why "build
    once, cache per playthrough" is implemented as an LRU keyed by schema
    shape, not a per-playthrough dict that would leak memory over time).
    """
    fields: dict[str, object] = {}
    for name, field_def in json.loads(schema_json).items():
        fields[name] = _field_to_pydantic_type(field_def)
    return create_model("GameState", **fields)  # type: ignore[call-overload]

def get_state_model(state_schema: dict[str, object], entity_attrs: dict[str, object]) -> type[BaseModel]:
    schema_hash = _schema_hash(state_schema, entity_attrs)
    return _build_model(schema_hash, json.dumps({"state": state_schema, "entities": entity_attrs}, sort_keys=True))
```

`_field_to_pydantic_type` handles the five supported shapes from `state_schema` (§4 of the demo scenario): primitives via `_TYPE_MAP` + `Field(ge=min, le=max)`; `entity_ref` as `str` (validated against known entity IDs at the service layer, not the type layer, since that set is scenario-specific data, not a type); `list` via `list[<item type>]`; nested `object` via a recursively-built sub-model; `derived` fields are `excluded=True`/read-only (present for shape validation, never accepted as direct tool input — enforced in `tool_handler.py`, not here).

#### Tool definitions (`app/turn/tool_definitions.py`):

```python
"""Fixed generic tool set for master-mode Gemini function-calling.

Deliberately generic (not per-scenario dynamic schemas) per the locked
decision — these five tools work against any scenario's state_schema shape.
Discipline against wasteful/trivial calls lives in each description's text,
not a mechanical gate — see master-mode-demo-scenario.md §12 for a worked
example and the Q&A record in the spec commit history for the reasoning.
"""

from google.genai import types

TOOL_SET_FIELD = types.FunctionDeclaration(
    name="set_field",
    description=(
        "Set a state field to an exact value. Use only when the player's "
        "action would meaningfully and durably change tracked state — never "
        "for flavor/descriptive narration with no lasting effect."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "path": types.Schema(type=types.Type.STRING),
            "value": types.Schema(type=types.Type.STRING),
        },
        required=["path", "value"],
    ),
)

TOOL_ADJUST_NUMERIC_FIELD = types.FunctionDeclaration(
    name="adjust_numeric_field",
    description=(
        "Increment or decrement a numeric field by a delta (e.g. damage, "
        "healing, reputation shifts). Use only for a real, consequential "
        "change — not routine flavor."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "path": types.Schema(type=types.Type.STRING),
            "delta": types.Schema(type=types.Type.NUMBER),
        },
        required=["path", "delta"],
    ),
)

TOOL_ADD_INVENTORY_ITEM = types.FunctionDeclaration(
    name="add_inventory_item",
    description="Add an obtainable item entity to an inventory list field.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "path": types.Schema(type=types.Type.STRING),
            "entity_id": types.Schema(type=types.Type.STRING),
        },
        required=["path", "entity_id"],
    ),
)

TOOL_ROLL_DICE = types.FunctionDeclaration(
    name="roll_dice",
    description=(
        "Roll dice for a genuinely uncertain, consequential outcome — a real "
        "skill check or contested action. Never for routine or narratively "
        "assured actions."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "sides": types.Schema(type=types.Type.INTEGER),
            "modifier": types.Schema(type=types.Type.INTEGER),
        },
        required=["sides"],
    ),
)

MASTER_MODE_TOOLS = types.Tool(
    function_declarations=[
        TOOL_SET_FIELD,
        TOOL_ADJUST_NUMERIC_FIELD,
        TOOL_ADD_INVENTORY_ITEM,
        TOOL_ROLL_DICE,
    ]
)
```

`roll_dice` is handled entirely inside `tool_handler.py` (pure computation, no state mutation, no validation needed) — its result is fed back as a function response so Gemini can react to it, per the walkthrough in the demo scenario's §12.

#### Hidden fact filtering (`context_retrieval.py` addition):

```python
def _filter_hidden(facts: list[Fact], revealed_fact_ids: set[str]) -> list[Fact]:
    return [f for f in facts if not f.hidden or str(f.fact_id) in revealed_fact_ids]
```

#### On-scene entity narrator instructions (heuristic, implemented in `ai_orchestrator.py`'s prompt builder):

An entity's `narrator_instruction` is included in the system instruction for a turn when either: (a) the entity's `entity_id` appears as `subject` or `object` in this turn's (post-hidden-filter) retrieved facts, or (b) any `entity_ref`-typed state field currently points at it (e.g. `player.location == "hollow_cairn"` surfaces `hollow_cairn`'s instruction, if it had one). No new infrastructure — reuses `context_retrieval`'s output and the already-loaded state.

### 3.5. Git & Review Workflow

- Branch: `feat/master-mode-turn-pipeline`
- Depends on `master-mode-data-model.spec.md` merged first (needs the entities/facts/end_conditions/rule_invariants tables and the Core API endpoints to author test fixtures against).
- Commit scope: one commit for `game_state.py`/`tool_call.py` models, one for `condition_evaluator.py`, one for `state_validator.py` + `tool_handler.py`, one for the `ai_orchestrator.py`/`gemini_client.py` tool-calling extension, one for the `pipeline.py` wiring + Core API `scenario_snapshot` extension.
- PR checklist: newbie-mode turn tests still pass unmodified (this spec must not regress the existing working path); master-mode turn tests cover the full "Hollow Cairn" walkthrough end-to-end against a mocked Gemini.

### 3.6. Boundaries (Three-Tier Model)

- ✅ **Always:** validate every proposed mutation against the cached Pydantic model **and** every applicable `rule_invariants` row before it touches `Playthrough.state`; log `tool_call_count` per turn (informational, non-blocking) per the locked discipline-not-mechanical-gate decision; keep `condition_evaluator` running before `context_retrieval`/`ai_orchestrator`, never after.
- ⚠️ **Ask First:** changing the tool-call round-trip cap from 5; adding a sixth generic tool beyond the four listed here; changing the derived-field convention (currently read-only, computed server-side, never a valid tool-call target).
- 🚫 **Never:** let `tool_handler.py` or `condition_evaluator.py` call `gemini_client` directly (only `ai_orchestrator.py` may); let a validation failure silently pass through as if it succeeded; let `state_writer` persist state that skipped `state_validator`.

## 4. Edge Cases, Rate Limits & Graceful Degradation

- **Tool-call cap hit:** on the 6th round-trip attempt, `ai_orchestrator` stops offering tools (drops `MASTER_MODE_TOOLS` from the next `generate_with_tools` call, forcing a plain text completion) rather than aborting the turn — the player still gets narration and a `done` event, just without further mechanical effect from that turn's excess calls. Logged as `EVENT_TOOL_CALL_CAP_HIT` with the round-trip count, so a scenario that habitually hits the cap is visible to whoever's tuning its `narrator_persona`.
- **Invariant violated by a type/range-valid mutation:** the failure returned to Gemini as a function-response error must name which invariant failed in player-appropriate terms (drawn from `rule_invariants.narrator_text`, not a raw Pydantic validation error string) — Gemini needs enough signal to recover narratively, not a stack trace.
- **`condition_evaluator` mutation collides with a rule invariant:** an Effect C mutation is still checked by `state_validator` immediately after being applied, same as an AI tool-call mutation — if a creator authors a condition whose own mutation would violate their own invariant, it's rejected and logged as a scenario-authoring bug (`EVENT_EFFECT_C_INVARIANT_VIOLATION`), not silently applied. This should never happen if the Studio's real-time validation (`master-mode-studio-ui.spec.md`) does its job, but the backend doesn't trust that alone.
- **Gemini timeout/failure mid-tool-call-loop:** reuses the existing `GeminiUnavailableError`/retry path from `ai_orchestrator.py` — a transient failure mid-loop retries the *current* call, not the whole loop from scratch (already-applied, already-validated mutations from earlier round-trips in this turn are not rolled back, since `state_writer` hasn't persisted anything yet — the whole in-progress working-state stays in memory until the turn either completes or the top-level retry budget is exhausted, matching the existing "turn is not committed" degradation behavior in the README).
- **Entity referenced in state but deleted mid-playthrough:** cannot happen — entity deletion cascades to facts (data-model spec) but an entity referenced by a *state field value* (e.g. `player.location`) isn't itself deleted by editing a scenario, since active playthroughs are pinned to `scenario_snapshot` (ADR-8) and never see the live `entities` table again after creation.

## 5. Phased Implementation Tasks (Task Checklist)

- [ ] **Task 1 (Expression evaluator + game state model):** Implement `turn/expression_evaluator.py` (shared grammar: comparison, AND/OR/NOT, in/contains, string match) and `models/game_state.py` (dynamic model builder + LRU cache) and `models/tool_call.py` (tool call/result Pydantic shapes: `ProposedMutation`, `ValidationResult`, `ToolCallLogEntry`). Verify: `pytest tests/turn/test_expression_evaluator.py tests/models/test_game_state.py`.
- [ ] **Task 2 (Condition evaluator):** Implement `turn/steps/condition_evaluator.py` — active conditions, Effect C pre-turn mutation, field-relevance scoping, using `expression_evaluator`. Verify: `pytest tests/turn/steps/test_condition_evaluator.py`.
- [ ] **Task 3 (State validator):** Implement `turn/steps/state_validator.py` — schema validation via `game_state.get_state_model()` plus `rule_invariants` checks via `expression_evaluator`. Verify: `pytest tests/turn/steps/test_state_validator.py`.
- [ ] **Task 4 (Tool handler):** Implement `turn/steps/tool_handler.py` — translates a Gemini function call into a `ProposedMutation`; implements `roll_dice` computation directly (no state touch). Verify: `pytest tests/turn/steps/test_tool_handler.py`.
- [ ] **Task 5 (Gemini tool-calling wiring):** Add `generate_with_tools()` to `gemini_client.py`; extend `ai_orchestrator.py` with the round-trip loop, cap handling, and on-scene entity instruction injection. Verify: `pytest tests/turn/steps/test_ai_orchestrator.py`; confirm newbie-mode tests still pass unmodified.
- [ ] **Task 6 (Hidden fact filtering):** Add `hidden` to `models/memory.py`'s `Fact`; filter in `context_retrieval.py`. Verify: `pytest tests/turn/steps/test_context_retrieval.py`.
- [ ] **Task 7 (Pipeline + snapshot wiring):** Wire `condition_evaluator` into `pipeline.py` (master-mode-conditional); extend Core API's `playthrough_service.py` snapshot construction. Verify: an end-to-end master-mode turn test against "The Hollow Cairn" fixture completes with the expected `state_update` event.
