# AI-DND — Agent Coding Guidelines

> **Read this file before touching any file in this repository.**
> These rules apply to every file, every service, every language. No exceptions unless explicitly noted.

---

## Project Context

**What this is:** An engine and platform for creating and playing text-based AI-driven games. Two modes: *newbie* (freeform lore, AI narrates freely) and *master* (fully structured game state — stats, factions, win/lose conditions — that the AI narrator must respect via tool-calling).

**Core product loop:** Creator authors a scenario → publishes it → players discover and start a playthrough → an AI narrator (Gemini) drives the story turn by turn, backed by a graph-based memory layer for world consistency → playthroughs are shareable for spectating or multiplayer.

**Three services in this monorepo:**

| Service | Path | Purpose |
|---|---|---|
| Frontend | `apps/frontend/` | React + Vite + TypeScript. Two surfaces: Studio (authoring) and Play (discovery + gameplay). |
| Core API | `apps/core-api/` | Python + FastAPI. Auth, scenario CRUD, publish flow, discovery, playthroughs, ratings. Stateless request/response only. No AI calls. No streaming. |
| Turn Resolution Service (TRS) | `apps/turn-resolution-service/` | Python + FastAPI. Orchestrates the per-turn gameplay loop: validates action → loads state → retrieves memory → calls Gemini → validates tool calls → streams narration → persists state. The only service with AI calls and SSE streaming. |

**External dependencies:**
- **Gemini (Vertex AI)** — AI narrator. Called only from `apps/turn-resolution-service/app/integrations/gemini_client.py`.
- **Memory layer** — World fact storage and retrieval. Called only from `integrations/memory_client.py` in each service that needs it.
- **PostgreSQL via Cloud SQL** — Single source of truth. All durable state lives here.
- **Firebase Auth** — Token issuance. Both services validate tokens on every request.

---

## Universal Rules

These apply to every file in every service regardless of language.

### Structure & Complexity

- **Maximum nesting depth: 2 levels.** If you need a third level, extract a function.
- **Functions under 30 lines.** If a function is longer, it is doing more than one thing. Split it.
- **Single responsibility per function.** A function that performs I/O (database read, HTTP call) must not also perform data transformation. Split into two functions: one that fetches, one that transforms.
- **No nested ternaries.** One ternary per expression maximum. Use `if/else` for anything more complex.
- **No magic numbers or strings.** Name constants explicitly. Put them in `config.py` (Python) or `constants/` (TypeScript).

### Naming

- **No single-letter variable names** except loop indices (`i`, `j`, `k`).
- **Boolean variables must be prefixed** with `is_`, `has_`, `should_`, or `can_`. Examples: `is_published`, `has_active_conditions`, `should_flush_batch`.
- **Functions named for what they return or do**, not how they do it. `get_scenario_by_id` not `query_db_for_scenario`.
- **No abbreviations** unless universally understood (`id`, `url`, `api`, `db`, `sse`, `llm`).

### Comments and Documentation

- **No comments that restate what the code does.** `# increment turn count` above `turn_count += 1` is noise. Delete it.
- **Docstrings only for:** public API functions/endpoints, non-trivial business logic that requires explaining *why* (not *what*), and any regex or mathematical expression.
- **Inline comments only for:** explaining a non-obvious decision, a known limitation, or a deliberate trade-off. Start with `# NOTE:` or `# TRADE-OFF:` to make intent clear.

### Error Handling

- **No bare `except:` (Python) or empty `catch (e) {}` (TypeScript).** Every caught exception must be handled explicitly.
- **Raise or return explicit domain exceptions** from `app/exceptions/`. Example: raise `NotFoundError` not a generic `ValueError`. In TypeScript, throw typed errors or return `Result` objects.
- **Never swallow errors silently.** Log at minimum before continuing.

### Formatting — run after every file modification

- **Python:** `ruff format .` then `ruff check . --fix`
- **TypeScript:** `prettier --write .` then `eslint . --fix`

---

## Python Rules (Core API + Turn Resolution Service)

### Types and Models

- **Type hints on every function** — parameters and return type. No untyped signatures.
- **Pydantic v2 models for all request/response shapes.** No raw `dict` crossing service boundaries.
- **`Optional[T]` written as `T | None`** (Python 3.10+ union syntax).
- **Never use `Any` from `typing`.** If the shape is truly unknown, use `dict[str, object]` and validate explicitly.

### Async

- **All I/O is async.** No synchronous database calls, HTTP calls, or file reads in an async context.
- **Never use `asyncio.run()` inside an async function.**
- **Never block the event loop.** CPU-heavy work goes in `asyncio.run_in_executor`.

### Architecture Layer Rules — enforced strictly

```
Router → Service → Repository → Database
```

- **Routers** call services only. No repository calls, no SQL, no business logic in routers.
- **Services** call repositories only. No raw SQL. No direct database connections.
- **Repositories** are the only files that write SQL. One repository per database entity.
- **Never skip a layer.** A router never calls a repository directly. A service never builds a raw SQL string.

### Configuration

- **Environment variables are read only in `config.py`.** No `os.environ.get()` scattered elsewhere. Other modules import from `config.py`.

### Exceptions

- Custom exceptions live in `app/exceptions/`. Every domain has its own exceptions file (e.g., `scenario_exceptions.py`). All inherit from `app/exceptions/base.py`.
- Services raise domain exceptions. Routers catch them and map to HTTP responses in `middleware/error_handler.py`.

### Logging

- Use structured logging (`structlog` or Python's `logging` with JSON formatter). No `print()` statements in production code.
- Log at the service layer, not the repository layer. Repositories are dumb data access — they do not log.

---

## TypeScript / React Rules (Frontend)

### Types

- **TypeScript strict mode is always on.** Do not disable strict checks.
- **No `any`.** Use `unknown` and narrow with type guards, or define a proper interface.
- **Props interfaces named `{ComponentName}Props`** and colocated in the component's `.types.ts` file.
- **API response types live in `feature/types/` or `shared/types/`.** Never define the same shape twice.

### Component Rules

- **One component per file.** A file named `ScenarioCard.tsx` exports exactly one component: `ScenarioCard`.
- **Components are pure where possible.** No side effects in the render body.
- **Event handlers prefixed with `handle`.** Examples: `handleSubmit`, `handleKeyDown`, `handleTurnSubmit`.
- **No inline styles.** Tailwind utility classes only. If a style repeats across components, extract a Tailwind component class in `globals.css`.
- **Conditional rendering uses early returns,** not deeply nested ternaries.

### State Management

- **React Query for all server state.** No `useEffect` + `useState` pattern for data fetching. Every API call has a corresponding React Query hook in `feature/hooks/`.
- **Zustand for client-only UI state** (active turn indicator, SSE connection status, panel open/closed). Zustand stores are flat — no nested state objects. One store file per feature.
- **Do not put server state in Zustand.** If it comes from an API, it belongs in React Query.

### SSE Connections

- **SSE connections are managed only through `shared/hooks/useSSE.ts`.** Never instantiate `EventSource` directly in a component or feature hook. Feature-level hooks (`useTurnStream`, `useNotifications`, `useSpectator`) wrap `useSSE`.

### Feature Boundaries

- **Features never import from each other.** `studio/` never imports from `play/` and vice versa. Cross-feature shared code goes into `shared/` first.
- **`shared/` contains no feature-specific logic.** If a component knows what a `Scenario` is for business reasons, it belongs in a feature, not `shared/`.

### Hooks

- Custom hooks are prefixed with `use`.
- A hook file exports exactly one hook.
- A hook that wraps a React Query call is named after the resource: `useScenario`, `usePlaythrough`.

---

## Architecture Boundaries — Never Violate

These are hard constraints derived from the RFC. Violating them breaks the system's separation of concerns.

| Boundary | Rule |
|---|---|
| **Gemini calls** | Only from `apps/turn-resolution-service/app/integrations/gemini_client.py`. Nowhere else. |
| **Memory layer calls** | Only from `integrations/memory_client.py` in each service that needs it. Nowhere else. |
| **SQL** | Only in `repositories/`. Never in services, routers, or middleware. |
| **Environment variables** | Only read in `config.py`. Imported by everything else. |
| **TRS writing to `Scenario`** | TRS may only increment `Scenario.play_count` at turn 10. It never writes any other field on `Scenario`. |
| **Turn pipeline step order** | `pipeline.py` is the only file that knows step order. Steps in `steps/` never call each other. |
| **Frontend features** | Features never import from sibling features. Only from `shared/`. |
| **SSE in frontend** | Raw `EventSource` never appears outside `shared/lib/sse-client.ts`. |
| **Schema duplication** | A Pydantic model or TypeScript type is defined once. If two parts of the system need the same shape, the type is shared, not duplicated. |

---

## Testing Rules

### Python

- **Every new endpoint gets an integration test** using `pytest-asyncio` before the task is considered done.
- **Mock external network calls** (Gemini API, memory layer HTTP calls) using `respx` or `httpx` mock transports.
- **Do not mock the database** in integration tests. Integration tests run against a real test Postgres instance.
- **Test file mirrors source file.** `tests/services/test_scenario_service.py` tests `app/services/scenario_service.py`.
- **Unit test pure business logic** in services that has no I/O dependencies.

### TypeScript

- **React Testing Library only.** No direct DOM manipulation in tests.
- **No snapshot tests for logic components.** Snapshots are only acceptable for purely presentational leaf components that will never change.
- **Mock API calls at the network level** using `msw` (Mock Service Worker), not by mocking React Query internals.
- **Test user behaviour, not implementation details.** Test what the user sees and does, not which function was called.

---

## Performance Rules

### Python

- **No N+1 queries.** If fetching a list of entities that each need related data, use a join or `selectinload`. Never query inside a loop.
- **Async DB connections always.** Use an async connection pool (`asyncpg` or SQLAlchemy async). Never use synchronous drivers in an async FastAPI app.
- **SSE responses stream immediately.** Never buffer the full Gemini response before sending. `yield` tokens as they arrive. A buffered SSE response is a bug.

### TypeScript

- **Lazy load heavy routes.** Use `React.lazy` + `Suspense` for Studio and Play pages — they should not be in the initial bundle.
- **React Query cache times are set intentionally.** The discovery feed has a short `staleTime`. A player's own playthrough state has `staleTime: 0` (always fresh). Never leave cache configuration at the library default without a conscious decision.
- **No unnecessary re-renders.** Zustand selectors are granular — subscribe to only the slice of state the component needs, not the whole store.

---

## What Good Output Looks Like

When you modify a file, the result should:

1. Pass `ruff format` + `ruff check` (Python) or `prettier` + `eslint` (TypeScript) with zero warnings.
2. Have no function longer than 30 lines.
3. Have no nesting deeper than 2 levels.
4. Have no untyped function signatures.
5. Have no duplicated type definitions.
6. Not violate any architecture boundary listed above.
7. Include or update the relevant integration test if an endpoint was added or changed.
