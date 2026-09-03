# Spec: Playthrough Sharing (Spectate/Join) + Multiplayer Turn Notifications

## 1. Objective & User Outcome
- **Problem Statement:** The RFC's sharing and multiplayer model is designed and partially scaffolded (`PlaythroughShare` ORM model exists and is registered; TRS's `request_receiver.py` already enforces turn order server-side) but has no reachable surface: Core API's `share_service.py`, `share_repo.py`, `routers/share.py`, `models/share.py` are all 0-byte files and not mounted; there is no `GET /v1/playthroughs/{id}/turns` scrollback endpoint; TRS's `session/notification_manager.py`, `session/spectator_manager.py`, and `routers/session.py` are all 0-byte files and not mounted. A player cannot generate a share link, join a playthrough, load turn history, or receive/see a live spectate stream or a "your turn" notification today.
- **User Story:** As a playthrough owner, I want to generate a spectate link and a join link so others can watch or play with me; as an invited player, I want to join via that link and be told when it's my turn; as a spectator, I want to watch narration arrive live without being able to act.
- **Success Criteria:**
  - `POST /v1/playthroughs/{id}/share` (Core API) issues/returns a `spectate` or `join` token; reissuing the same mode returns the existing token (RFC: "implementation may return existing token").
  - `POST /v1/playthroughs/join` (Core API) creates a `Participant` with `role: joined` and the next `turn_order_position`, rejecting solo-only scenarios and non-active playthroughs.
  - `GET /v1/playthroughs/{id}/turns` (Core API) returns paginated `TurnLog` entries, accessible to participants and valid share-token holders.
  - `GET /v1/session/{id}/spectate` (TRS) streams the same `narration`/`done` events as a live turn, read-only, gated on a valid `spectate` token.
  - `GET /v1/session/{id}/notifications` (TRS) is a persistent SSE channel emitting `your_turn` after each turn completes in a multiplayer playthrough.
  - Turn-order enforcement (already built in `request_receiver.py`) is exercised for real once a second participant can actually join.

## 2. Technical Architecture & Data Flow
- **Components Involved:**
  - **Core API — Share (`app/models/share.py`, `app/repositories/share_repo.py`, `app/services/share_service.py`, `app/routers/share.py`, all filled in):** issues/validates `PlaythroughShare` tokens (`secrets.token_urlsafe`, per the RFC's "unguessable token" requirement — not a sequential ID).
  - **Core API — Join (`routers/playthroughs.py`, modified; reuses `share_service`):** `POST /v1/playthroughs/join` validates a `join`-mode token via `share_service`, then creates a `Participant` via the existing `ParticipantRepo`.
  - **Core API — Turn history (`routers/playthroughs.py`, modified; `services/playthrough_service.py`, modified):** `GET /v1/playthroughs/{id}/turns`, paginated (`page`, `page_size`, `from_turn`), reusing `TurnLogRepo` (already exists per the file-structure convention — confirm/create if missing) with an index-friendly query on `(playthrough_id, turn_number)`.
  - **Core API — Auth for share/spectate access (`middleware/`, modified or new dependency):** a new auth dependency that accepts *either* a normal bearer token (existing participant) *or* a valid `share_token` query param, since the RFC requires spectators to access `GET /v1/playthroughs/{id}` and `/turns` without being a participant. Every endpoint still requires auth in some form — the RFC states "no anonymous access, including spectators" — so a spectate token counts as identity here, not a bypass.
  - **TRS — `PlaythroughShare` read-only mirror (`app/db/models/share.py`, `app/repositories/share_repo.py`, new):** TRS has no DB access to `PlaythroughShare` today. Per this app's existing pattern — TRS already keeps its own read-only ORM mirrors of `Participant`/`Playthrough`/`Scenario`/`TurnLog` (same tables Core API owns, same Postgres instance, both services just have their own SQLAlchemy model classes pointed at it) — this spec adds a matching read-only `PlaythroughShare` mirror rather than introducing a new cross-service HTTP call. `share_repo.py` here exposes only `get_by_token(share_token)`; TRS never writes to this table (share creation stays exclusively a Core API concern).
  - **TRS — Session (`app/session/notification_manager.py`, `app/session/spectator_manager.py`, filled in; `app/routers/session.py`, filled in; `app/main.py`, modified):**
    - `spectator_manager.py`: subscribes a spectator connection to the same narration events a live turn produces. Since TRS's turn responses are per-request SSE (ADR-2) and not a shared broadcast today, the simplest correct approach — and the one this spec commits to — is an in-process async pub/sub keyed by `playthrough_id`: `pipeline.py`'s `_run_turn_events` publishes each `narration`/`done` event to a per-playthrough broadcast queue in addition to yielding it to the acting player's own stream; `spectator_manager.py` subscribes a new spectator connection to that same queue.
    - `notification_manager.py`: a long-lived SSE connection per participant (RFC: persistent, not per-request per ADR-2). Maintains an in-process map of `playthrough_id → {participant_id: queue}`. `state_writer.py` (TRS turn pipeline, modified) publishes a `your_turn` event to the *next* participant's queue immediately after a successful write, computed the same way `request_receiver._validate_turn_order` already computes "whose turn is it."
  - **Explicitly single-process scope:** both managers use in-process memory (a module-level dict), consistent with this stack's Cloud Run single-container deployment for the hackathon and with how the memory-mock decision (decoupled, in-process) was already made — this is not designed to survive a multi-instance deployment; that's a known, stated limitation, not an oversight.

- **Sequence Flow — Share + Join:**
  1. Owner calls `POST /v1/playthroughs/{id}/share {mode: "spectate"}` → Core API returns `{share_token, url}`. Same for `mode: "join"`.
  2. A second player opens the join URL, frontend calls `POST /v1/playthroughs/join {share_token}` → Core API validates the token's mode is `join`, the playthrough is `active`, and `scenario.player_count_support != "solo"`; creates a `Participant` with the next `turn_order_position`.
  3. Both participants can now call `POST /v1/turn` (TRS) with their own `participant_id`; `request_receiver.py`'s existing turn-order check now has real teeth.

- **Sequence Flow — Spectate:**
  1. A viewer opens the spectate URL, frontend calls `GET /v1/playthroughs/{id}/turns` (Core API, with the share token) to backfill history, then opens `GET /v1/session/{id}/spectate` (TRS, with the share token) for live narration.
  2. When any participant's turn produces narration, `spectator_manager` relays the same `narration`/`done` events to every subscribed spectator connection for that `playthrough_id`.

- **Sequence Flow — Multiplayer notification:**
  1. Each participant's client opens `GET /v1/session/{id}/notifications` on page load (persistent connection, per ADR-2).
  2. After `state_writer.write_turn(...)` succeeds in the TRS pipeline, it computes the next participant (reusing `request_receiver`'s turn-order logic, extracted to a shared helper) and calls `notification_manager.notify_next_turn(playthrough_id, next_participant_id)`.
  3. That participant's open `/notifications` connection emits `your_turn`; other participants' connections stay silent.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- **Core API test:** `cd apps/core-api && pytest tests/services/test_share_service.py tests/routers/test_share_router.py tests/routers/test_playthrough_router.py -v`
- **TRS test:** `cd apps/turn-resolution-service && pytest tests/session/ tests/routers/test_session.py -v`
- **Lint (both):** `ruff format . && ruff check . --fix`

### 3.2. Testing Strategy & Conformance
- **Core API:**
  1. `POST /v1/playthroughs/{id}/share {mode: spectate}` — creates and returns a token; a second call with the same mode returns the *same* token (no duplicate row).
  2. `POST /v1/playthroughs/join` — valid `join` token, multiplayer-eligible scenario → new `Participant`, `turn_order_position` = existing count + 1.
  3. `POST /v1/playthroughs/join` — scenario `player_count_support == "solo"` → rejected (400/409).
  4. `POST /v1/playthroughs/join` — playthrough `status != "active"` → rejected.
  5. `POST /v1/playthroughs/join` — invalid/unknown token → 404.
  6. `GET /v1/playthroughs/{id}/turns` — paginated correctly (`page_size`, `from_turn`); participant access succeeds; a random authenticated non-participant without a share token is rejected; a valid spectate-token holder succeeds without being a `Participant`.
- **TRS:**
  7. `spectator_manager`: two async subscribers on the same `playthrough_id` both receive an event published to that playthrough's queue; a subscriber on a *different* `playthrough_id` receives nothing.
  8. `notification_manager`: `notify_next_turn` delivers `your_turn` only to the target participant's queue, not others.
  9. `GET /v1/session/{id}/spectate` — invalid/missing share token → 401/403 before any subscription happens.
  10. Pipeline integration (extend existing `test_pipeline.py`): after a successful turn in a 2-participant playthrough, the correct next participant's notification queue receives exactly one `your_turn` event.
- Per CLAUDE.md, integration tests run against real test Postgres; the in-process pub/sub queues are exercised directly with `asyncio` test helpers (no real network needed for that half).

### 3.3. Project Structure & File Layout
- **Core API — files filled in (previously empty):**
  - `apps/core-api/app/models/share.py`
  - `apps/core-api/app/repositories/share_repo.py`
  - `apps/core-api/app/services/share_service.py`
  - `apps/core-api/app/routers/share.py`
- **Core API — files modified:**
  - `apps/core-api/app/routers/playthroughs.py` — add `POST /v1/playthroughs/join`, `GET /v1/playthroughs/{id}/turns`.
  - `apps/core-api/app/services/playthrough_service.py` — add `join_playthrough(...)`, `list_turns(...)`.
  - `apps/core-api/app/repositories/turn_log_repo.py` — create if it doesn't already exist (per file-structure convention it should; confirm during implementation).
  - `apps/core-api/app/main.py` — `app.include_router(share.router)`.
  - `apps/core-api/app/middleware/auth.py` — add a share-token-aware auth dependency.
  - `apps/core-api/app/exceptions/playthrough_exceptions.py` — add `InvalidShareTokenError`, `SoloScenarioJoinError`, `PlaythroughNotJoinableError`.
- **Core API — tests created:**
  - `apps/core-api/tests/services/test_share_service.py`
  - `apps/core-api/tests/routers/test_share_router.py`
  - Extend `apps/core-api/tests/routers/test_playthrough_router.py` for join + turns.
- **TRS — files created:**
  - `apps/turn-resolution-service/app/db/models/share.py` (read-only `PlaythroughShare` mirror, matching the existing `Participant`/`Playthrough`/`Scenario` mirror pattern)
  - `apps/turn-resolution-service/app/repositories/share_repo.py` (`get_by_token(...)` only — no writes)
  - `apps/turn-resolution-service/app/exceptions/session_exceptions.py` (or extend an existing exceptions file — `InvalidShareTokenError`)
- **TRS — files filled in (previously empty):**
  - `apps/turn-resolution-service/app/session/notification_manager.py`
  - `apps/turn-resolution-service/app/session/spectator_manager.py`
  - `apps/turn-resolution-service/app/routers/session.py`
- **TRS — files modified:**
  - `apps/turn-resolution-service/app/main.py` — `app.include_router(session.router)`.
  - `apps/turn-resolution-service/app/turn/pipeline.py` — publish narration/done events to `spectator_manager`; call `notification_manager.notify_next_turn(...)` after a successful write.
  - `apps/turn-resolution-service/app/turn/steps/request_receiver.py` — extract `_next_participant(...)` as a reusable helper (currently private/inline logic) so `notification_manager` wiring can reuse it without duplicating the turn-order math.
- **TRS — tests created:**
  - `apps/turn-resolution-service/tests/session/test_notification_manager.py`
  - `apps/turn-resolution-service/tests/session/test_spectator_manager.py`
  - `apps/turn-resolution-service/tests/routers/test_session.py`

### 3.4. Code Style & Interfaces

**`apps/core-api/app/models/share.py`:**
```python
"""Pydantic request/response schemas for playthrough sharing."""

import uuid
from pydantic import BaseModel, ConfigDict


class ShareCreate(BaseModel):
    mode: str  # "spectate" | "join" — validated against PlaythroughShare's check constraint


class ShareResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    share_token: str
    mode: str
    playthrough_id: uuid.UUID
    url: str


class JoinRequest(BaseModel):
    share_token: str
```

**`apps/core-api/app/services/share_service.py` (core method):**
```python
async def create_or_get_share(self, playthrough_id: uuid.UUID, mode: str) -> PlaythroughShare:
    """Return the existing token for (playthrough_id, mode) if one exists, else create it."""
    existing = await self._share_repo.get_by_playthrough_and_mode(playthrough_id, mode)
    if existing:
        return existing
    token = secrets.token_urlsafe(32)
    return await self._share_repo.create(playthrough_id=playthrough_id, mode=mode, share_token=token)


async def validate_token(self, share_token: str, required_mode: str | None = None) -> PlaythroughShare:
    """Look up a token; raise InvalidShareTokenError if missing or mode mismatched."""
    share = await self._share_repo.get_by_token(share_token)
    if share is None or (required_mode and share.mode != required_mode):
        raise InvalidShareTokenError()
    return share
```

**TRS `app/session/spectator_manager.py` (core shape):**
```python
"""In-process pub/sub relaying live turn events to spectator SSE connections.

Single-process scope only (see spec §2) — not designed for multi-instance
deployment.
"""

import asyncio
import uuid

_subscribers: dict[uuid.UUID, list[asyncio.Queue]] = {}


def subscribe(playthrough_id: uuid.UUID) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(playthrough_id, []).append(queue)
    return queue


def unsubscribe(playthrough_id: uuid.UUID, queue: asyncio.Queue) -> None:
    _subscribers.get(playthrough_id, []).remove(queue)


async def publish(playthrough_id: uuid.UUID, event: dict[str, str]) -> None:
    for queue in _subscribers.get(playthrough_id, []):
        await queue.put(event)
```

**TRS `app/routers/session.py`:**
```python
"""FastAPI router for multiplayer notifications and spectator streaming."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse

from app.session import notification_manager, spectator_manager

router = APIRouter(prefix="/v1/session", tags=["Session"])


@router.get("/{playthrough_id}/spectate")
async def spectate(playthrough_id: uuid.UUID, share_token: Annotated[str, Query()]) -> EventSourceResponse:
    """Read-only live narration stream, gated on a valid spectate share token."""
    await _validate_spectate_token(playthrough_id, share_token)  # calls Core API or shares a validation contract — see §6
    queue = spectator_manager.subscribe(playthrough_id)
    return EventSourceResponse(_relay(queue))


@router.get("/{playthrough_id}/notifications")
async def notifications(playthrough_id: uuid.UUID, participant_id: uuid.UUID) -> EventSourceResponse:
    """Persistent SSE channel for 'your_turn' / 'participant_joined' / 'playthrough_ended'."""
    queue = notification_manager.subscribe(playthrough_id, participant_id)
    return EventSourceResponse(_relay(queue))
```
`_validate_spectate_token` resolves via the new read-only `share_repo.get_by_token(...)` mirror described in §2 — no cross-service HTTP call. Raise a `403`-mapped domain exception (`InvalidShareTokenError`, mirroring TRS's existing exception style in `turn_exceptions.py`) if the token is missing, unknown, or not `mode == "spectate"`, or if its `playthrough_id` doesn't match the path parameter.

### 3.5. Git & Review Workflow
- **Branch name:** `feat/sharing-and-multiplayer`
- **Commit scope:** Core API share/join/turns as one logical unit (can be 2-3 commits), TRS session managers as a separate unit — these can land as two PRs if preferred, since they're independently testable and Core API's share endpoints are useful even before TRS's spectate/notifications exist.
- **PR validation checklist:**
  - [ ] Share tokens are generated with `secrets.token_urlsafe`, never sequential/guessable
  - [ ] `POST /v1/playthroughs/join` rejects solo scenarios and non-active playthroughs with the correct exception types
  - [ ] TRS session managers are in-process only — no new external service dependency introduced
  - [ ] `notification_manager`/`spectator_manager` don't leak queues (unsubscribe on disconnect — test via a `finally`/context-manager pattern in the router)

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** generate unguessable tokens; validate `mode` against the DB check constraint's allowed values in Pydantic too (fail fast); require some form of auth (bearer token or valid share token) on every endpoint — no anonymous access, per RFC.
- ⚠️ **Ask First:** any change to the `PlaythroughShare` table's *writable* surface — TRS's mirror is read-only by design (`share_repo.py` exposes only `get_by_token`); if a future need arises for TRS to write share state, that's a new decision, not an extension of this one.
- 🚫 **Never:** let the in-process pub/sub queues silently grow unbounded (always unsubscribe on client disconnect); let a spectator connection accept turn submissions (`POST /v1/turn` stays participant-only, unrelated to spectate tokens); let TRS's `PlaythroughShare` mirror perform any write.

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Spectator connects before any turn has happened:** `spectate` stream simply waits — no backfill logic needed here since the frontend is expected to call `GET /v1/playthroughs/{id}/turns` first for history (per RFC: "Spectators load turn history separately... then connect here to follow the live session").
- **Notification target participant never connects (no open `/notifications` stream):** `publish`/`notify_next_turn` silently no-ops (nothing subscribed to that queue) — this is expected and fine; the frontend's turn-order UI state doesn't depend on having received a push notification to function (RFC: "backend check is a safety net, not a substitute for correct UI").
- **Two join attempts race on the same token:** the second racing request should still succeed (multiple participants can join the same scenario) unless `player_count_support` or `status` rules reject it — this isn't a single-use-token scenario like the RFC's ratings gate; no idempotency lock is required here.
- **Owner requests a share link for `mode: join` on a solo-only scenario:** allowed at share-creation time (RFC doesn't forbid generating the link); the rejection happens at `POST /v1/playthroughs/join`, matching the RFC's stated failure point exactly.

## 5. Phased Implementation Tasks (Task Checklist)
- [x] **Task 1 (Core API share module):** `models/share.py` (mode typed as `Literal["spectate", "join"]`), `repositories/share_repo.py`, `services/share_service.py` (also does the participant-only access check, not just token issuance), `routers/share.py`, mounted in `main.py`. `test_share_service.py` (7 tests) and `test_share_router.py` (6 tests) pass.
- [x] **Task 2 (Core API join + turns):** extended `playthrough_service.py` (`join_playthrough`, `list_turns`, injected `share_repo`/`turn_log_repo`) and `routers/playthroughs.py` (`POST /join`, `GET /{id}/turns`). Filled in two more previously-empty files this required: `repositories/turn_log_repo.py` and `models/turn_log.py`. Extended `test_playthrough_router.py` (3 new tests) pass; updated `test_playthrough_service.py`'s constructor call for the two new dependencies.
- [x] **Task 3 (Core API share-aware auth):** decided against a new dependency — reused the existing `get_optional_current_user` (already in `middleware/auth.py`) plus an optional `share_token` query param, with the accept-either logic living in `PlaythroughService._require_turns_access`, not the router. Simpler than inventing new auth machinery for one endpoint.
- [x] **Task 4 (TRS PlaythroughShare mirror):** `db/models/share.py`, `repositories/share_repo.py` (`get_by_token` only, no writes), `exceptions/session_exceptions.py`. Registered in `db/models/__init__.py`.
- [x] **Task 5 (TRS spectator_manager + notification_manager):** in-process pub/sub (module-level dicts keyed by playthrough_id / (playthrough_id, participant_id)). `test_spectator_manager.py` (4 tests) and `test_notification_manager.py` (4 tests) pass. Also extracted `turn_order.expected_participant` out of `request_receiver.py` into a shared `app/turn/turn_order.py` so both files use identical turn-order math, per the spec's own design.
- [x] **Task 6 (TRS routers/session.py + pipeline wiring):** mounted in `main.py`; `pipeline.py` now publishes `narration`/`done` events to `spectator_manager` as they're yielded and calls `notification_manager.notify_next_turn(...)` after a successful write (multiplayer only). Added `app/session/access.py` for the router-level token/participant validation (keeps repo instantiation out of the router itself, matching how `pipeline.py` owns repo instantiation for the turn router). `test_session.py` (4 tests) passes; extended `test_pipeline.py` with a 2-participant test confirming the correct next participant's queue receives exactly one `your_turn` event.
- [x] **Task 7 (Full regression, both services):** Core API 81/81 pass (up from 65), TRS 67/67 pass (up from 54), no regressions in either. `ruff format` + `ruff check` clean on every file touched in both services (pre-existing, unrelated lint findings in `auth.py`/`auth_service.py`/`test_auth.py` left untouched, same ones noted in the migration spec).
