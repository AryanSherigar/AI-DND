# TRS Architecture — Middleware & Schemas

This document details the cross-cutting HTTP middleware and Pydantic schemas in `apps/turn-resolution-service/app/middleware/` and `app/models/`.

---

## 1. Middleware Layer (`app/middleware/`)

### `apps/turn-resolution-service/app/middleware/auth.py`
- **Purpose & Layer:** Bearer token authentication dependency.
- **Key Functions:**
  - `get_current_user(request, credentials)`: Extracts JWT or dev header (`x-dev-user-id`). Verifies signatures and returns `CurrentUser(user_id=UUID)`.
  - Binds `user_id` into `structlog.contextvars`.

### `apps/turn-resolution-service/app/middleware/error_handler.py`
- **Purpose & Layer:** Global exception interceptor for TRS.
- **Key Functions:**
  - Translates domain exceptions (`TurnException`, `GeminiUnavailableError`, `StateWriteError`) into structured HTTP RFC 7807 responses when non-streaming endpoints fail.

### `apps/turn-resolution-service/app/middleware/request_context.py`
- **Purpose & Layer:** Distributed tracing header propagator (`X-Request-Id`). Binds request IDs to structlog context.

---

## 2. Pydantic Models & Schemas (`app/models/`)

### `apps/turn-resolution-service/app/models/game_state.py`
- **Purpose & Layer:** Dynamic runtime Pydantic model synthesis for arbitrary scenario schemas.
- **Key Exports & Functions:**
  - `get_state_model(state_schema: dict) -> type[BaseModel]`: Compiles and caches a custom Pydantic model for scenario state using `pydantic.create_model`.
  - `get_entity_attribute_model(attributes_schema: dict) -> type[BaseModel]`: Dynamically compiles attribute validation models for specific entity types.
  - Caching strategy: Uses `@lru_cache(maxsize=256)` keyed on the SHA-256 hash of the schema JSON. Allows multiple concurrent playthroughs of the same scenario to reuse pre-compiled validation classes.

### `apps/turn-resolution-service/app/models/tool_call.py`
- **Purpose & Layer:** AI function calling schema representations and execution result envelopes.
- **Key Models:**
  - `ParsedToolCall`: Raw tool invocation parsed from Gemini stream (`call_id`, `name`, `arguments: dict[str, object]`).
  - `MasterModeTurnResult`: Result envelope carrying validated state mutations, updated flags, applied conditions, and tool execution logs.

### `apps/turn-resolution-service/app/models/turn.py`
- **Purpose & Layer:** Turn execution request and response shapes.
- **Key Models:**
  - `TurnRequestInput`: Inbound payload (`playthrough_id: UUID`, `action: str`, `character_id: UUID | None`).
  - `TurnRequest`: Validated internal representation passed to `pipeline.py`.
  - `LoadedState`: In-memory container holding loaded playthrough, scenario, participants, and history window.
  - `TurnStreamChunk`: Chunk yielded by `ai_orchestrator` containing text token, mood tag, or tool call.

### `apps/turn-resolution-service/app/models/assistant.py`
- **Purpose & Layer:** Studio assistant co-author chat schemas.
- **Key Models:**
  - `AssistantDraftContext`: Holds current authoring form fields (title, logline, lore, opening scene, active wizard section).
  - `AssistantChatMessage`: Individual conversation turn (`role: "user" | "model"`, `content: str`).
  - `AssistantChatRequest`: Array of history messages, draft context, and prompt.

### `apps/turn-resolution-service/app/models/memory.py`
- **Purpose & Layer:** Runtime query and ingest contracts for the external graph memory service.
