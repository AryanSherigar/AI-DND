# Spec: Master-Mode Minigames — Interstitial Trigger System & Replit Partner Integration

## 1. Objective & User Outcome

- **Problem Statement:** Master-mode scenarios have two ways to produce mechanical consequences today: `scenario_conditions` (Effect A/C — narrator instructions and single-field deterministic mutations, evaluated every turn) and `end_conditions` (win/lose, terminates the playthrough). Neither lets a creator drop the player into a genuinely distinct interstitial *experience* — a timed skill challenge, a puzzle, a third-party mini-app — whose outcome then feeds back into the story. This spec adds **minigames**: a new scenario sub-resource that triggers, the same way an end condition does, against post-turn state; hands control to a full-screen experience entirely outside the AI narration loop; and resolves by submitting a result as the player's next action, which the existing pipeline turns into a deterministic state mutation plus an AI-narrated consequence. Two authoring paths ship in this build: a curated, built-in dodge/survival minigame, and a **Replit-embed** path where a creator builds and hosts their own minigame on Replit and we live-embed it during play — this repo's hackathon partner-track integration.
- **User Story:** As a creator, I want to declare "when the player enters the ambush clearing, trigger the Ashfall Dodge challenge — winning grants the Ember Charm, losing costs 15 health" (or: "...trigger my own Replit-hosted rune-matching game"), and have that challenge actually run as a real interstitial sequence during play, with its outcome mechanically applied and narrated, without writing any pipeline code myself.
- **Success Criteria:**
  - A master-mode scenario can have zero or more `scenario_minigames`, each with its own `trigger_condition_expression` (same grammar as `scenario_conditions`/`end_conditions`) and `priority`; the first matching minigame on a given turn triggers, evaluated after that turn's AI tool-call loop against final state.
  - Triggering a minigame **never involves Gemini** — narration for the triggering turn completes normally, then a new SSE event hands the client a self-contained play-time config; the AI narrator is not invoked again until the result is submitted.
  - A creator picks per-minigame between `binary` (win/lose mutation) and `tiered` (score-range → mutation) outcome modes, plus a `timeout_mutation` used only when the minigame fails to resolve normally (e.g. an unreachable Replit URL). Mutations use the existing `StateMutation` shape (`app/models/condition.py`) — imported, never redefined.
  - `minigame_type` is `dodge` (one curated, built-in, PixiJS-rendered dodge/survival arena — full design in `docs/specs/dodge-minigame-design.spec.md`) or `replit_embed` (a creator-supplied deployed Repl URL, live-embedded in a sandboxed iframe, communicating results via a `postMessage` contract and a starter SDK this repo ships).
  - A minigame trigger is **solo-only**: it never fires when a playthrough has more than one participant. It is **master-mode only**, matching `entities`/`scenario_conditions`/`end_conditions`/`rule_invariants`.
  - While a minigame is pending resolution, the playthrough rejects any turn submission that isn't that minigame's result, and rejects a result submission that doesn't match the pending minigame — a playthrough can never have two minigames pending, and can never silently drop one.
  - If a minigame trigger and an end condition would both match the same turn, the minigame wins — end-condition evaluation is skipped that turn; the playthrough can still end on the turn immediately after the result comes back.
  - No content-moderation pipeline exists for creator-submitted Replit URLs; standard cross-origin iframe sandboxing (`sandbox="allow-scripts allow-same-origin allow-forms"`) is the only protection — an explicit, accepted hackathon-scope boundary, not an oversight.
  - All new/modified files pass `ruff format . && ruff check . --fix` (Python) / `prettier --write . && eslint . --fix` (TypeScript) with zero warnings, respect Router → Service → Repository → DB layering, and every new endpoint has an integration test per CLAUDE.md.

## 2. Technical Architecture & Data Flow

- **Components Involved:** Core API (`app/routers/minigames.py`, `app/services/minigame_service.py`, `app/repositories/minigame_repo.py`, new migration, `app/services/playthrough_service.py`), TRS (`app/turn/pipeline.py`, two new steps, `app/models/turn.py`, `app/turn/steps/request_receiver.py`, `app/turn/steps/response_streamer.py`, `app/turn/steps/end_condition_evaluator.py`), Frontend (`shared/types/minigame.types.ts`, `shared/hooks/useReplitHandshake.ts`, `features/studio/components/MinigameEditor/`, `features/play/components/MinigameOverlay/`, `features/play/stores/play.store.ts`), and a new top-level `replit-template/` runnable artifact.
- **Depends on:** `master-mode-data-model.spec.md` (`state_schema`, `entities`, `scenario_conditions` grammar) and `master-mode-turn-pipeline.spec.md` (`expression_evaluator`, `state_validator`, the working AI tool-call loop) merged first. Mirrors, but does not modify, `master-mode-end-conditions.spec.md`'s evaluator shape; adds one new guard to it (skip on a fresh minigame trigger).
- **Reference data:** "The Hollow Cairn" (`docs/specs/master-mode-demo-scenario.md`) could add one `dodge` minigame at the warden's ambush ("Warden's Onslaught" — lose costs health, win grants a tactical advantage flag) as a worked example during implementation; not required to exist for this spec to land.

- **Sequence Flow — authoring (`POST /v1/scenarios/{id}/minigames`):**
  1. Creator opens the new "Minigames" tab, builds a trigger condition with the existing `ExpressionBuilder`, picks `minigame_type` (`dodge` or `replit_embed`), sets outcome mode and mutations.
  2. Router validates request shape, delegates to `MinigameService.create_minigame`.
  3. `MinigameService` runs `_ensure_master_mode_owner` (rejects newbie-mode scenarios and non-owners, same guard name/shape as `MapService`), validates the `minigame_type`/config pairing (`dodge_config` xor `replit_embed_url`) and the `outcome_mode`/mutation pairing (`binary` requires both `win_mutation`/`lose_mutation`, `tiered` requires ≥1 `tiered_outcomes` entry) via a Pydantic cross-field `model_validator`.
  4. For `replit_embed`: the service performs a bounded, `tenacity`-retried HTTP reachability check against `replit_embed_url` (2-3 attempts with backoff, to ride out a sleeping free-tier Repl's cold start) before persisting; an unreachable URL raises `MinigameUnreachableError` (422). This is a save-time confidence check, distinct from and complementary to Studio's client-side "Test Connection" handshake (§2, Studio flow below) — it confirms HTTP reachability even if the creator forgot to wire up the SDK's `ready()` call.
  5. `MinigameRepo` inserts the row; service returns `MinigameResponse`.

- **Sequence Flow — Studio "Test Connection" (client-side only, no new backend call):** creator pastes a `replit_embed_url`, clicks "Test Connection"; `ReplitTestConnectionButton` renders a hidden iframe with that `src`, and `useReplitHandshake` (shared hook, §3.4) waits up to ~10s for a `minigame:ready` postMessage, showing a pass/fail indicator. Independent of the save-time reachability check above — one confirms HTTP reachability, the other confirms the SDK actually wired up.

- **Sequence Flow — playthrough creation:** `PlaythroughService._build_snapshot` (already extended by prior master-mode specs) additionally copies this scenario's `scenario_minigames` (priority-ascending) into `scenario_snapshot["scenario_minigames"]`, inside the existing `if scenario.mode == "master":` block. No `state_schema` injection is needed (unlike Maps) — the pending-minigame marker is not a creator-facing state field; see §2's pipeline flow.

- **Sequence Flow — one master-mode turn where a minigame triggers:**
  1. Player submits a normal action; the turn proceeds exactly as today through `condition_evaluator` → `context_retrieval` → `ai_orchestrator`'s Gemini tool-call loop, narration streaming as usual.
  2. **New `minigame_trigger_evaluator` step**, positioned where `map_state_sync` runs (after the tool-call loop's `working_state` is final, before `state_writer`): if `participant_count == 1` and no minigame is already pending, evaluates `scenario_snapshot["scenario_minigames"]` in priority order against `working_state` (same `_try_evaluate`-wrapped, never-blocks-play pattern as `end_condition_evaluator`). On the first match, stamps the **full** play-time payload into `working_state["_pending_minigame"]`. For a matched `replit_embed` minigame, also fires a short, bounded pre-warm HTTP ping at `replit_embed_url` (`tenacity`-retried, capped total budget of a few seconds so it never meaningfully delays the SSE stream) — best-effort only; failure here does not block the trigger.
  3. `state_writer` persists `working_state` (including `_pending_minigame`) verbatim — no code change to `state_writer.py` itself.
  4. `end_condition_evaluator` is skipped this turn if `_pending_minigame` was just stamped (new guard, one added `if`).
  5. After the normal `turn_summary_event`, `pipeline.py` yields a new `minigame_event` SSE event carrying `{minigame_id, minigame_type, label, dodge_config | replit_embed_url, timeout_seconds}` — never the mutation/outcome config, which stays server-side only — then the usual `done_event`.
  6. Client receives `minigame_event`, buffers it (mirrors the existing `pending_chapter_delta` pattern in `play.store.ts`), and on `done` promotes it to `active_minigame`, rendering `MinigameOverlay` full-screen. No further Gemini calls happen while this is showing.
  7. Player finishes the minigame (or it times out after one retry). The overlay closes immediately; the client calls `submitMinigameResult`, POSTing `{action_kind: "minigame_result", minigame_result: {minigame_id, outcome_tag, score?}}` to the same `/v1/turn` endpoint.
  8. `request_receiver` validates the submission matches the pending minigame (new gating logic, §3.4).
  9. **New `minigame_result_resolver` step**, positioned where `condition_evaluator` runs (after `state_loader`, before `context_retrieval`): looks up the matching mutation (`win_mutation`/`lose_mutation`/a `tiered_outcomes` range/`timeout_mutation`), applies it via the same `state_paths.set_field_value` + `state_validator.validate_applied_change` pair `condition_evaluator` uses for Effect C, appends the token-substituted `narrator_instruction_template` into `active_instructions`, and clears `_pending_minigame` — unconditionally, even on a malformed/missing mutation (never leaves a playthrough stuck).
  10. The turn continues completely normally from here — `ai_orchestrator` picks up `active_instructions` exactly as it already does for any active condition (**zero changes to `ai_orchestrator.py`**), Gemini narrates the outcome in-fiction and may make further tool calls, `state_writer` persists, `end_condition_evaluator` runs as usual (the playthrough can end on this turn if the minigame's outcome satisfied an end condition).

## 3. The Six Core Engineering Dimensions

### 3.1. Commands

- Core API build check (from `apps/core-api/`): `python3 -c "import fastapi, pydantic, sqlalchemy, alembic, tenacity"`
- Core API test: `pytest tests/services/test_minigame_service.py tests/routers/test_minigame_router.py -v`
- Core API migration: `alembic upgrade head` (applies `008_master_mode_minigames.py`); `alembic downgrade -1` must cleanly reverse it.
- TRS test: `pytest tests/turn/steps/test_minigame_trigger_evaluator.py tests/turn/steps/test_minigame_result_resolver.py tests/turn/test_pipeline_minigames.py -v` (from `apps/turn-resolution-service/`)
- Frontend type-check: `npx tsc --noEmit` (from `apps/frontend/`)
- Frontend test: `npx vitest run src/features/studio/components/MinigameEditor src/features/play/components/MinigameOverlay src/shared/hooks/useReplitHandshake`
- Lint/Format: `ruff format . && ruff check . --fix` (Python) / `npx prettier --write . && npx eslint . --fix` (TypeScript)

### 3.2. Testing Strategy & Conformance

- **Location:** `apps/core-api/tests/{services,repositories,routers}/test_minigame_*.py`; `apps/turn-resolution-service/tests/turn/steps/test_minigame_*.py`, `tests/turn/test_pipeline_minigames.py`; `apps/frontend/src/features/{studio,play}/components/**/__tests__/`, `apps/frontend/src/shared/hooks/__tests__/`.
- **Mocking:** Core API tests run against a real test Postgres (never mock the DB), and mock the outbound reachability-check HTTP call (`respx`/`httpx` mock transport) rather than hitting a real Replit URL. TRS mocks Gemini via SDK-level mocks and mocks the pre-warm ping's HTTP client the same way. Frontend mocks network calls with `msw` and mocks `postMessage`/iframe `load` events directly (no real Replit dependency in CI).
- **Required cases:**
  - **Master-mode-only enforcement:** `POST /v1/scenarios/{newbie_id}/minigames` returns `MinigameModeError` (422); the same request against a master-mode scenario succeeds.
  - **Outcome-shape validation:** creating a `binary` minigame with `tiered_outcomes` non-empty is rejected; creating a `tiered` minigame with no `tiered_outcomes` entries is rejected; creating a `dodge` minigame with `replit_embed_url` set is rejected; creating a `replit_embed` minigame with `dodge_config` set is rejected.
  - **Reachability check:** an unreachable `replit_embed_url` (mocked 5xx/timeout on every retry attempt) is rejected with `MinigameUnreachableError`; a URL that fails once then succeeds (mocked) is accepted, proving the retry actually retries.
  - **Priority ordering / first-match-wins:** two minigames whose triggers are both true on the same state — only the lower-`priority` one's payload is stamped into `_pending_minigame`.
  - **Solo-only gate:** a minigame whose trigger is true is not stamped when `participant_count > 1` (assert no `minigame_event` is yielded, no `_pending_minigame` written).
  - **Pending-minigame gating:** a normal action submitted while `_pending_minigame` is set is rejected with `MinigameResultRequiredError`; a `minigame_result` submission with a mismatched `minigame_id`, or submitted when nothing is pending, is rejected with `MinigameResultMismatchError`.
  - **End-condition suppression:** a turn where both a minigame trigger and an end condition would match — assert `end_condition_evaluator.evaluate_end_conditions` is not called that turn (spy/call-count assertion), and the minigame's `minigame_event` is still yielded normally.
  - **Result resolution — binary:** submitting `outcome_tag: "win"` applies `win_mutation` exactly, injects the token-substituted `narrator_instruction_template` into `active_instructions`, and clears `_pending_minigame`; `outcome_tag: "lose"` applies `lose_mutation` instead.
  - **Result resolution — tiered:** a `score` falling in a given `tiered_outcomes` range applies that range's mutation; a `score` outside all ranges applies no mutation but still clears `_pending_minigame` and logs a warning (never blocks the turn).
  - **Result resolution — timeout:** `outcome_tag: "timeout"` applies `timeout_mutation`.
  - **Malformed/missing mutation:** a minigame whose matched mutation references an invalid `state_schema` path fails `state_validator.validate_applied_change` gracefully — no mutation applied, `_pending_minigame` still cleared, a generic fallback narrator instruction used, turn does not fail.
  - **Snapshot inclusion:** creating a playthrough for a scenario with 2 minigames produces `scenario_snapshot["scenario_minigames"]` sorted by `priority` ascending.
  - **SSE payload boundary:** `minigame_event`'s serialized payload never contains `win_mutation`/`lose_mutation`/`tiered_outcomes`/`timeout_mutation`/`narrator_instruction_template` keys (explicit negative assertion on the JSON payload).
  - **`useReplitHandshake` origin validation:** a `message` event whose `origin` doesn't match the configured `replit_embed_url`'s origin is ignored, even with a well-formed `minigame:result` payload.
  - **`MinigameOverlay` reload resume:** given `PlaythroughData.pending_minigame` populated from `state._pending_minigame`, the overlay renders on mount without waiting for a new SSE event.
  - **`MinigameEditor` scenario-type gating:** the "Minigames" tab is present in `MasterModeStudioLayout` only, never in `StudioDocumentLayout`.

### 3.3. Project Structure & File Layout

**Files to create (Core API):**
- `apps/core-api/app/db/models/scenario_minigame.py`
- `apps/core-api/app/models/minigame.py` (`MinigameCreate/Update/Response`, `DodgeConfig`, `TieredOutcomeRange`, `MinigameReorderRequest`)
- `apps/core-api/app/repositories/minigame_repo.py`
- `apps/core-api/app/services/minigame_service.py`
- `apps/core-api/app/routers/minigames.py`
- `apps/core-api/app/exceptions/minigame_exceptions.py`
- `apps/core-api/app/db/migrations/versions/008_master_mode_minigames.py`
- `apps/core-api/tests/services/test_minigame_service.py`, `tests/routers/test_minigame_router.py`, `tests/repositories/test_minigame_repo.py`

**Files to modify (Core API):**
- `apps/core-api/app/db/models/__init__.py` — register `ScenarioMinigame`.
- `apps/core-api/app/services/playthrough_service.py` — add `_snapshot_minigames`, called inside the existing `mode == "master"` branch of `_build_snapshot`; inject `MinigameRepo` into `PlaythroughService.__init__`.
- `apps/core-api/app/main.py` — register `minigames.py` router.
- `apps/core-api/pyproject.toml` — add `tenacity` dependency (already present in TRS, not yet in Core API).

**Files to create (TRS):**
- `apps/turn-resolution-service/app/turn/steps/minigame_trigger_evaluator.py`
- `apps/turn-resolution-service/app/turn/steps/minigame_result_resolver.py`
- `apps/turn-resolution-service/app/models/minigame_event.py` (`MinigameEventPayload`, `MinigameResultInput`)
- `apps/turn-resolution-service/tests/turn/steps/test_minigame_trigger_evaluator.py`, `test_minigame_result_resolver.py`, `tests/turn/test_pipeline_minigames.py`

**Files to modify (TRS):**
- `apps/turn-resolution-service/app/turn/pipeline.py` — wire both new steps at the positions described in §2; suppress `end_condition_evaluator` on a fresh trigger; hoist the participant-count query earlier for the solo-only gate (reuse in the existing `_notify_next_participant` call, avoiding a duplicate query); update the module docstring with the new step order.
- `apps/turn-resolution-service/app/turn/steps/end_condition_evaluator.py` — add the one-line suppression guard.
- `apps/turn-resolution-service/app/turn/steps/request_receiver.py` — pending-minigame gating (reads `Playthrough.state` already fetched with the row, no new query).
- `apps/turn-resolution-service/app/turn/steps/response_streamer.py` — add `minigame_event(payload: MinigameEventPayload) -> ServerSentEvent`.
- `apps/turn-resolution-service/app/models/turn.py` — `TurnRequestInput` gains `action_kind`/`minigame_result`.
- `apps/turn-resolution-service/app/exceptions/turn_exceptions.py` — add `MinigameResultRequiredError`, `MinigameResultMismatchError`.
- `apps/turn-resolution-service/app/config.py` — add `minigame_iframe_handshake_timeout_seconds: int = 20`.

**Files to create (Replit template):**
- `replit-template/index.html`, `replit-template/style.css`, `replit-template/game.js`
- `replit-template/minigame-sdk.js`
- `replit-template/README.md`
- `replit-template/.replit` (+ whichever companion Replit config file this generation expects — verify during implementation)

**Files to create (Frontend):**
- `apps/frontend/src/shared/types/minigame.types.ts`
- `apps/frontend/src/shared/hooks/useReplitHandshake.ts`
- `apps/frontend/src/features/studio/api/minigames.api.ts`
- `apps/frontend/src/features/studio/hooks/useMinigames.ts`
- `apps/frontend/src/features/studio/types/minigame.types.ts`
- `apps/frontend/src/features/studio/components/MinigameEditor/{MinigameEditor,MinigameRow,MinigameForm,DodgeDifficultySlider,ReplitTestConnectionButton,TieredOutcomeRow}.tsx` (+ `.types.ts` each)
- `apps/frontend/src/features/play/hooks/useMinigameResult.ts`
- `apps/frontend/src/features/play/components/MinigameOverlay/MinigameOverlay.tsx` (+ `.types.ts`)
- `apps/frontend/src/features/play/components/MinigameOverlay/ReplitEmbed/{ReplitEmbedMinigame,IframeLoadingState}.tsx` (+ `.types.ts`)
- `apps/frontend/src/features/play/components/MinigameOverlay/DodgeMinigame/**` — file layout specified separately in `docs/specs/dodge-minigame-design.spec.md`

**Files to modify (Frontend):**
- `apps/frontend/src/features/studio/components/Layout/MasterModeStudioLayout.types.ts` — add `{ id: "minigames", label: "Minigames" }` to `MASTER_MODE_TABS`.
- `apps/frontend/src/features/studio/components/Layout/MasterModeStudioLayout.tsx` — render `MinigameEditor` when `activeTab === "minigames"`.
- `apps/frontend/src/features/studio/components/ConditionEditor/StateMutationFields.tsx` (+ `.types.ts`) — add `isOptional?: boolean` prop (default `true`), hiding the "has mutation" checkbox and rendering fields unconditionally when `false`.
- `apps/frontend/src/features/play/stores/play.store.ts` — `minigame`/`done` SSE handling (buffer-then-promote pattern), `active_minigame`/`pending_minigame_trigger` state, `submitMinigameResult`/`clearActiveMinigame` actions.
- `apps/frontend/src/features/play/types/play.types.ts` — `PlaythroughData.pending_minigame`.
- `apps/frontend/src/features/play/pages/PlayPage.tsx` (or wherever the master-mode play surface composes its panels) — render `MinigameOverlay` when `active_minigame` is set.

### 3.4. Code Style & Interfaces

#### Migration (`008_master_mode_minigames.py`), following `007_master_mode_maps.py`'s conventions:

```python
def _create_scenario_minigames_table() -> None:
    op.create_table(
        "scenario_minigames",
        sa.Column("minigame_id", postgresql.UUID(as_uuid=True),
                   server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("scenarios.scenario_id", ondelete="CASCADE"),
                   nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("minigame_type", sa.String(length=20), nullable=False),
        sa.Column("trigger_condition_expression", postgresql.JSONB(),
                   server_default="{}", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("outcome_mode", sa.String(length=10), nullable=False),
        sa.Column("win_mutation", postgresql.JSONB(), nullable=True),
        sa.Column("lose_mutation", postgresql.JSONB(), nullable=True),
        sa.Column("tiered_outcomes", postgresql.JSONB(),
                   server_default="[]", nullable=False),
        sa.Column("timeout_mutation", postgresql.JSONB(), nullable=True),
        sa.Column("narrator_instruction_template", sa.Text(), nullable=True),
        sa.Column("dodge_config", postgresql.JSONB(), nullable=True),
        sa.Column("replit_embed_url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                   server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                   server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "minigame_type IN ('dodge', 'replit_embed')",
            name="ck_scenario_minigames_type",
        ),
        sa.CheckConstraint(
            "outcome_mode IN ('binary', 'tiered')",
            name="ck_scenario_minigames_outcome_mode",
        ),
        sa.CheckConstraint(
            "(minigame_type = 'dodge' AND replit_embed_url IS NULL) OR "
            "(minigame_type = 'replit_embed' AND dodge_config IS NULL)",
            name="ck_scenario_minigames_type_config_pairing",
        ),
    )
    op.create_index(
        "idx_scenario_minigames_scenario_id", "scenario_minigames", ["scenario_id"]
    )
```

`upgrade()` calls this helper; `downgrade()` drops the index then the table, matching `007`'s discipline. Outcome-mode/mutation-shape pairing (`binary` ⇔ win+lose set, `tiered` ⇔ non-empty `tiered_outcomes`) is intentionally **not** a DB-level CHECK — same posture as `scenario_conditions.state_mutation`'s internal shape today — and is enforced in Pydantic instead (below).

#### Pydantic schemas (`app/models/minigame.py`):

```python
import uuid
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.condition import StateMutation

class TieredOutcomeRange(BaseModel):
    min_score: int
    max_score: int
    mutation: StateMutation

class DodgeConfig(BaseModel):
    difficulty: int = Field(..., ge=1, le=5)

class MinigameCreate(BaseModel):
    label: str = Field(..., max_length=255)
    minigame_type: str = Field(..., pattern="^(dodge|replit_embed)$")
    trigger_condition_expression: dict[str, object]
    priority: int = 0
    outcome_mode: str = Field(..., pattern="^(binary|tiered)$")
    win_mutation: StateMutation | None = None
    lose_mutation: StateMutation | None = None
    tiered_outcomes: list[TieredOutcomeRange] = Field(default_factory=list)
    timeout_mutation: StateMutation | None = None
    narrator_instruction_template: str | None = None
    dodge_config: DodgeConfig | None = None
    replit_embed_url: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="after")
    def _validate_shape(self) -> "MinigameCreate":
        if self.minigame_type == "dodge" and (
            self.dodge_config is None or self.replit_embed_url is not None
        ):
            raise ValueError("dodge minigames require dodge_config, not replit_embed_url")
        if self.minigame_type == "replit_embed" and (
            not self.replit_embed_url or self.dodge_config is not None
        ):
            raise ValueError("replit_embed minigames require replit_embed_url, not dodge_config")
        if self.outcome_mode == "binary" and (
            self.win_mutation is None or self.lose_mutation is None or self.tiered_outcomes
        ):
            raise ValueError("binary outcome_mode requires win_mutation and lose_mutation, no tiered_outcomes")
        if self.outcome_mode == "tiered" and not self.tiered_outcomes:
            raise ValueError("tiered outcome_mode requires at least one tiered_outcomes entry")
        return self

class MinigameUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=255)
    trigger_condition_expression: dict[str, object] | None = None
    priority: int | None = None
    outcome_mode: str | None = Field(default=None, pattern="^(binary|tiered)$")
    win_mutation: StateMutation | None = None
    lose_mutation: StateMutation | None = None
    tiered_outcomes: list[TieredOutcomeRange] | None = None
    timeout_mutation: StateMutation | None = None
    narrator_instruction_template: str | None = None
    dodge_config: DodgeConfig | None = None
    replit_embed_url: str | None = Field(default=None, max_length=1024)

class MinigameResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    minigame_id: uuid.UUID
    scenario_id: uuid.UUID
    label: str
    minigame_type: str
    trigger_condition_expression: dict[str, object]
    priority: int
    outcome_mode: str
    win_mutation: StateMutation | None
    lose_mutation: StateMutation | None
    tiered_outcomes: list[TieredOutcomeRange]
    timeout_mutation: StateMutation | None
    narrator_instruction_template: str | None
    dodge_config: DodgeConfig | None
    replit_embed_url: str | None

class MinigameListResponse(BaseModel):
    items: list[MinigameResponse]

class MinigameReorderRequest(BaseModel):
    ordered_minigame_ids: list[uuid.UUID]
```

`StateMutation` is imported from `app.models.condition`, never redefined — the single-definition rule in practice.

#### `minigame_service.py`'s reachability check:

```python
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

async def _check_replit_reachable(self, url: str) -> None:
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=4)
        ):
            with attempt:
                response = await self._http_client.get(url, timeout=5.0)
                response.raise_for_status()
    except Exception as exc:
        raise MinigameUnreachableError(url=url) from exc
```

(`self._http_client` — an injected async HTTP client, following whatever pattern this codebase already uses for outbound HTTP in Core API services; verify and reuse rather than introducing a second HTTP-client convention during implementation.)

#### TRS `minigame_trigger_evaluator.py`:

```python
"""Evaluates scenario_minigames triggers against post-turn state.

Runs after the AI tool-call loop's working_state is built, before
state_writer (pipeline.py is the sole sequencer — this file does not call
state_writer or ai_orchestrator itself). Solo-only and master-mode-only,
first-match-wins by priority, mirroring end_condition_evaluator.py exactly.
"""

import structlog

from app.turn.expression_evaluator import evaluate

logger = structlog.get_logger()

EVENT_MINIGAME_TRIGGERED = "minigame_triggered"
EVENT_MINIGAME_EVALUATION_ERROR = "minigame_evaluation_error"
STATE_KEY_PENDING_MINIGAME = "_pending_minigame"


class MatchedMinigameTrigger:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload


def evaluate_trigger(
    minigames: list[dict[str, object]],
    final_state: dict[str, object],
    participant_count: int,
    timeout_seconds: int,
) -> MatchedMinigameTrigger | None:
    if participant_count > 1 or final_state.get(STATE_KEY_PENDING_MINIGAME):
        return None
    for minigame in minigames:
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


def _build_payload(minigame: dict[str, object], timeout_seconds: int) -> dict[str, object]:
    return {
        "minigame_id": minigame["minigame_id"],
        "minigame_type": minigame["minigame_type"],
        "label": minigame["label"],
        "dodge_config": minigame.get("dodge_config"),
        "replit_embed_url": minigame.get("replit_embed_url"),
        "timeout_seconds": timeout_seconds,
    }
```

`pipeline.py` wiring (mirrors the existing `is_master_mode` + maps-present branch style):

```python
if is_master_mode and participant_count == 1:
    matched_trigger = minigame_trigger_evaluator.evaluate_trigger(
        loaded_state.scenario_snapshot.get("scenario_minigames", []),
        working_state,
        participant_count,
        settings.minigame_iframe_handshake_timeout_seconds,
    )
    if matched_trigger:
        working_state["_pending_minigame"] = matched_trigger.payload
        if matched_trigger.payload["minigame_type"] == "replit_embed":
            await _prewarm_replit_url(matched_trigger.payload["replit_embed_url"])
```

(`_prewarm_replit_url` is a small `pipeline.py`-local async helper wrapping the same bounded `tenacity` retry pattern as the Core-API check, capped to a couple of seconds total — best-effort, exceptions swallowed and logged, never re-raised into the turn.)

#### TRS `minigame_result_resolver.py` — mirrors `condition_evaluator._apply_and_validate_effect_c`:

```python
"""Resolves a submitted minigame result into a state mutation + narrator
instruction, exactly like an active condition's Effect C, but triggered by
the incoming request's action_kind instead of an expression.

Runs after state_loader, before context_retrieval (master mode,
action_kind == "minigame_result" only).
"""

import structlog

from app.turn import state_paths
from app.turn.steps import state_validator

logger = structlog.get_logger()

EVENT_MINIGAME_RESOLVED = "minigame_resolved"
EVENT_MINIGAME_RESOLUTION_ERROR = "minigame_resolution_error"
FALLBACK_INSTRUCTION = "The trial concludes."


def resolve_result(
    minigames: list[dict[str, object]],
    state: dict[str, object],
    scenario_snapshot: dict[str, object],
    minigame_id: str,
    outcome_tag: str,
    score: int | None,
) -> tuple[dict[str, object], str]:
    state = dict(state)
    state.pop("_pending_minigame", None)

    minigame = next((m for m in minigames if m["minigame_id"] == minigame_id), None)
    if minigame is None:
        logger.warning(EVENT_MINIGAME_RESOLUTION_ERROR, minigame_id=minigame_id)
        return state, FALLBACK_INSTRUCTION

    mutation = _select_mutation(minigame, outcome_tag, score)
    if mutation:
        state = _apply_mutation(state, mutation, scenario_snapshot)

    template = minigame.get("narrator_instruction_template") or FALLBACK_INSTRUCTION
    instruction = _substitute_tokens(template, outcome_tag, score)
    logger.info(EVENT_MINIGAME_RESOLVED, minigame_id=minigame_id, outcome_tag=outcome_tag)
    return state, instruction


def _select_mutation(
    minigame: dict[str, object], outcome_tag: str, score: int | None
) -> dict[str, object] | None:
    if outcome_tag == "timeout":
        return minigame.get("timeout_mutation")
    if minigame["outcome_mode"] == "binary":
        return minigame.get("win_mutation" if outcome_tag == "win" else "lose_mutation")
    for tier in minigame.get("tiered_outcomes", []):
        if score is not None and tier["min_score"] <= score <= tier["max_score"]:
            return tier["mutation"]
    return None


def _apply_mutation(
    state: dict[str, object],
    mutation: dict[str, object],
    scenario_snapshot: dict[str, object],
) -> dict[str, object]:
    path = str(mutation.get("path") or "")
    if not path:
        return state
    candidate = state_paths.set_field_value(state, path, mutation.get("value"))
    result = state_validator.validate_applied_change(path, candidate, scenario_snapshot)
    return result.updated_state if result.is_valid else state


def _substitute_tokens(template: str, outcome_tag: str, score: int | None) -> str:
    return template.replace("{outcome_tag}", outcome_tag).replace(
        "{score}", str(score) if score is not None else ""
    )
```

(`_apply_mutation` intentionally omits `increment`/`decrement` op handling shown in `condition_evaluator._apply_effect_c_mutation` for brevity here — implementation must reuse that exact helper, or a shared one, rather than reimplement `set`/`increment`/`decrement` a third time; verify during implementation and factor `_apply_effect_c_mutation`'s op-handling into a shared `state_paths`-adjacent helper both steps call, rather than duplicating it.)

#### Frontend shared types (`shared/types/minigame.types.ts`):

```typescript
export type MinigameType = "dodge" | "replit_embed";
export type OutcomeMode = "binary" | "tiered";
export type MinigameOutcomeTag = "win" | "lose" | "timeout";

export interface StateMutationShape {
  path: string;
  op: "set" | "increment" | "decrement";
  value: unknown;
}

export interface MinigameEventPayload {
  minigame_id: string;
  minigame_type: MinigameType;
  label: string;
  dodge_config: { difficulty: number } | null;
  replit_embed_url: string | null;
  timeout_seconds: number;
}

export interface MinigameResultPayload {
  minigame_id: string;
  outcome_tag: MinigameOutcomeTag;
  score?: number;
}
```

`StateMutationShape` is the single shared source of truth for mutation shapes — during implementation, `ConditionEditor`'s existing mutation type must be re-exported from this file rather than kept as a parallel duplicate, since `MinigameEditor`'s outcome-mutation UI and `play/`'s types both need it and `play/` cannot import from `features/studio/types/`.

### 3.5. Git & Review Workflow

- Branch: `feat/master-mode-minigames`
- Depends on `master-mode-data-model.spec.md` and `master-mode-turn-pipeline.spec.md` merged first; touches (does not depend on being merged after) `master-mode-end-conditions.spec.md`'s evaluator.
- Commit scope: one commit for the migration + ORM model, one for the Core API minigame CRUD (service/repo/router/exceptions/reachability check), one for `playthrough_service.py` snapshot wiring, one for the TRS `TurnRequest`/exceptions/`request_receiver` gating, one for the two new TRS steps + pipeline wiring + SSE event, one for the shared frontend types/hooks, one for the Studio `MinigameEditor` tree (+ `StateMutationFields` prop addition), one for the Play `MinigameOverlay`/`ReplitEmbed` tree + store wiring, one for the `replit-template/` artifact (can land independently, any time after the postMessage contract below is final).
- PR checklist: `alembic upgrade head && alembic downgrade -1` clean; every new endpoint has a passing integration test against a real test Postgres; both new TRS steps have dedicated unit tests plus one pipeline-level integration test; existing newbie-mode, non-minigame master-mode, and end-condition turn tests still pass unmodified; `tsc --noEmit` and `eslint` clean; no `studio/`↔`play/` cross-imports outside `shared/`.

### 3.6. Boundaries (Three-Tier Model)

- ✅ **Always:** enforce `_ensure_master_mode_owner` on every Minigames endpoint; gate every trigger on `participant_count == 1`; clear `_pending_minigame` in `minigame_result_resolver` even when the mutation lookup fails; keep mutation/outcome config out of the `minigame_event` SSE payload; keep all SQL inside `repositories/`; validate the iframe's `postMessage` origin against the stored `replit_embed_url`'s origin before accepting any result.
- ⚠️ **Ask First:** allowing a minigame trigger in multiplayer playthroughs (reverses a locked product decision, not an implementation detail); adding any content-moderation/review step for `replit_embed_url` (reverses the accepted hackathon-scope trust posture); changing "minigame suppresses end conditions" to "both can fire" — a real semantic/demo-behavior change.
- 🚫 **Never:** let a tool call or Gemini set `_pending_minigame` directly (it is TRS-infrastructure-only, exactly like `_last_changed_fields`); let `minigame_trigger_evaluator`/`minigame_result_resolver` call `state_writer`/`ai_orchestrator`/each other directly; let the pre-warm ping's failure block or delay the turn beyond its capped budget; duplicate `MinigameEventPayload`/`StateMutationShape` between `studio/` and `play/` instead of importing from `shared/types/minigame.types.ts`.

## 4. Edge Cases, Rate Limits & Graceful Degradation

- **Scenario with zero minigames:** every minigame-aware code path (snapshot inclusion, trigger evaluation, SSE emission, overlay rendering) is a guarded no-op — a master-mode scenario that never uses Minigames behaves exactly as it does today.
- **Playthrough abandoned while a minigame is pending:** `_pending_minigame` simply sits unresolved in a dead playthrough's state — no cleanup job needed, since an abandoned playthrough never accepts further turns anyway (existing `request_receiver` status check).
- **Minigame deleted from the scenario after a playthrough's snapshot was frozen:** cannot happen mid-playthrough for *that* playthrough (ADR-8, snapshot immutability) — `minigame_result_resolver`'s "minigame not found in snapshot" fallback (§3.4) exists defensively, not for an expected case.
- **Both a minigame trigger and an end condition match the same turn:** minigame wins (locked decision); end-condition evaluation is skipped entirely that turn, re-evaluated normally starting the turn the result comes back.
- **Two minigames' triggers both true the same turn:** first-match-wins by ascending `priority`, identical semantics to `end_conditions` — should be flagged as a real-time Studio validation warning (likely an authoring mistake) per the existing pattern for end-condition collisions, not an error at evaluation time.
- **Replit URL becomes unreachable after being saved successfully (creator's Repl deleted/broken later):** the play-time client-side timeout/retry/`timeout_mutation` path (§2, sequence step 7) is the only safety net at play-time — the save-time reachability check only guarantees reachability *at save time*, not indefinitely; this is documented as an accepted limitation, not solved by periodic re-validation in this spec.
- **Creator's Replit page never calls `MinigameSDK.ready()`:** Studio's "Test Connection" shows a clear failure state; nothing prevents saving anyway (the save-time check is HTTP-reachability only, not SDK-wiring validation) — a creator can ship a broken minigame, discovered at play-time via the same timeout path.
- **Malformed `postMessage` payload from an embedded Repl:** `useReplitHandshake` ignores any message that doesn't match the expected `{type, ...}` shape or fails origin validation — never throws, never partially applies a malformed result.

## 5. Phased Implementation Tasks (Task Checklist)

- [ ] **Task 1 (Migration & ORM):** Write `008_master_mode_minigames.py` and `db/models/scenario_minigame.py`; register in `db/models/__init__.py`. Verify: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`.
- [ ] **Task 2 (Core API CRUD + reachability check):** Implement `models/minigame.py`, `repositories/minigame_repo.py`, `services/minigame_service.py` (incl. `_ensure_master_mode_owner`, shape validation, `tenacity`-backed reachability check), `routers/minigames.py`, `exceptions/minigame_exceptions.py`; add `tenacity` to `pyproject.toml`; register router in `main.py`. Verify: `pytest tests/services/test_minigame_service.py tests/routers/test_minigame_router.py`.
- [ ] **Task 3 (Snapshot wiring):** Extend `playthrough_service.py` with `_snapshot_minigames`, inject `MinigameRepo`. Verify: a snapshot fixture test confirms priority-sorted inclusion.
- [ ] **Task 4 (TRS request schema + gating):** Extend `models/turn.py`; add the two new exceptions; add pending-minigame gating to `request_receiver.py`. Verify: targeted unit tests for both gating branches.
- [ ] **Task 5 (TRS evaluator + resolver):** Implement `minigame_trigger_evaluator.py` and `minigame_result_resolver.py`; add the `end_condition_evaluator.py` suppression guard; add `minigame_event`/`MinigameEventPayload`; add the config constant. Verify: `pytest tests/turn/steps/test_minigame_trigger_evaluator.py tests/turn/steps/test_minigame_result_resolver.py`.
- [ ] **Task 6 (Pipeline wiring):** Wire both steps into `pipeline.py` at the documented positions, incl. the participant-count hoist and the pre-warm ping; update the module docstring. Verify: `pytest tests/turn/test_pipeline_minigames.py` asserting full trigger→SSE→result→resolution flow and SSE event ordering.
- [ ] **Task 7 (Frontend shared layer):** Implement `shared/types/minigame.types.ts` (incl. the `StateMutation` dedup with `ConditionEditor`) and `shared/hooks/useReplitHandshake.ts`. Verify: `npx vitest run src/shared/hooks/useReplitHandshake`.
- [ ] **Task 8 (Studio MinigameEditor):** Implement `studio/api/minigames.api.ts`, `studio/hooks/useMinigames.ts`, `studio/types/minigame.types.ts`, the `MinigameEditor/` tree, and the `StateMutationFields.tsx` `isOptional` prop; add the "Minigames" tab. Verify: `npx vitest run src/features/studio/components/MinigameEditor`; manual dev-server walkthrough authoring one of each `minigame_type`.
- [ ] **Task 9 (Play MinigameOverlay + Replit embed):** Implement `play.store.ts`/`play.types.ts` extensions, `useMinigameResult.ts`, `MinigameOverlay.tsx`, and the `ReplitEmbed/` subtree; wire into the play surface. Verify: `npx vitest run src/features/play/components/MinigameOverlay`; manual playthrough against a locally-served SDK-compliant stub page, confirming trigger → overlay → result → narrated outcome, reload-mid-minigame resume, and the timeout/retry/`timeout_mutation` path against a deliberately unreachable URL.
- [ ] **Task 10 (Dodge minigame):** Per `docs/specs/dodge-minigame-design.spec.md` — separate task sequence, implemented against that spec.
- [ ] **Task 11 (Replit template artifact):** Implement `replit-template/` per §3.3/§2's postMessage contract. Verify: manually fork/import into a real Replit account, confirm the demo game calls `MinigameSDK.ready()`/`reportResult()` correctly against a local test harness.
- [ ] **Task 12 (Docs closure):** `README.md` Non-Goals bullet, Partner Track section, Open Items entry, new ADR-10 — done last, after implementation settles any deviations from this spec.
