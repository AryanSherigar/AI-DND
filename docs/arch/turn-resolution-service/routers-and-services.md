# TRS Architecture — Routers & Services

This document details the HTTP routing and service modules in `apps/turn-resolution-service/app/routers/` and `app/services/`.

---

## 1. Overview & Streaming Contracts

TRS endpoints serve real-time Server-Sent Events (SSE) via Starlette's `EventSourceResponse`:
- **Immediate Streaming**: Handlers yield `ServerSentEvent` objects directly from async generators without in-memory buffering.
- **Header Injection**: Enforces `Content-Type: text/event-stream`, `Cache-Control: no-cache`, and `X-Accel-Buffering: no` for proxy compatibility.

---

## 2. File Profiles

### `apps/turn-resolution-service/app/routers/turn.py`
- **Purpose & Layer:** Primary gameplay action endpoint (`/v1/turn`).
- **Key Exports & Endpoints:**
  - `POST /v1/turn`: Accepts `TurnRequestInput` containing `playthrough_id`, `action`, `character_id`, and client state. Authenticates the player via `get_current_user`. Returns `EventSourceResponse(run_turn(turn_input, session))`.
- **Dependencies & Interactions:** Invokes `app/turn/pipeline.py` (`run_turn`).
- **Architecture Rules & Invariants:**
  - Never mutates database state directly in the router.
  - Returns `EventSourceResponse` with no intermediate buffering.

### `apps/turn-resolution-service/app/routers/session.py`
- **Purpose & Layer:** Real-time multiplayer session streaming (`/v1/session`).
- **Key Exports & Endpoints:**
  - `GET /v1/session/{playthrough_id}/spectate`: Gated by query parameter `share_token`. Validates spectator permissions via `access.validate_spectate_access`. Subscribes to `spectator_manager.subscribe(playthrough_id)` and streams real-time narration broadcasts to observers.
  - `GET /v1/session/{playthrough_id}/notifications`: Long-lived SSE connection for multiplayer participants. Validates participant ownership via `access.validate_notification_access`. Relays `"your_turn"` events from `notification_manager`.
- **Dependencies & Interactions:** Calls `app/session/access.py`, `spectator_manager.py`, and `notification_manager.py`.

### `apps/turn-resolution-service/app/routers/assistant.py`
- **Purpose & Layer:** Studio scenario authoring assistant chat endpoint (`/v1/studio/assistant`).
- **Key Exports & Endpoints:**
  - `POST /v1/studio/assistant`: Accepts `AssistantChatRequest` containing draft metadata and conversation history. Authenticates author and streams co-author guidance over SSE.
- **Dependencies & Interactions:** Calls `app/services/assistant_service.py` (`stream_assistant_chat`).

### `apps/turn-resolution-service/app/services/assistant_service.py`
- **Purpose & Layer:** Studio world-building co-pilot service.
- **Key Exports & Logic:**
  - `_BASE_PERSONA`: System instructions defining the assistant as an immersive world-building narrative consultant.
  - `_ACTION_SYNTAX_GUIDE`: Strict formatting protocol directing Gemini to wrap suggested draft elements in custom action blocks (`action:title`, `action:logline`, `action:lore`, `action:opening_prompt`, `action:story_card`, `action:style`, `action:instructions`).
  - `_format_draft_summary(draft: AssistantDraftContext) -> str`: Formats current wizard inputs into context for the LLM prompt.
  - `stream_assistant_chat(request: AssistantChatRequest) -> AsyncIterator[ServerSentEvent]`: Calls `gemini_client.generate_stream()` and yields formatted SSE chunks. Handles `GeminiUnavailableError` by emitting error events.
- **Dependencies & Interactions:** Calls `app/integrations/gemini_client.py`.
