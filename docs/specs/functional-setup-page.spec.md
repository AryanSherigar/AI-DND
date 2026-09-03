# Spec: Functional Scenario Setup Page & Playthrough Initialization

## 1. Objective & User Outcome
- **Problem Statement:** The scenario setup screen (`/setup/:id`) is currently driven by static mock data and local mock transitions without calling the backend. Submitting setup inputs does not create a durable `Playthrough` record or clone memory space templates.
- **User Story:** As a logged-in player initializing a published scenario, I want to fill in custom setup inputs (single select, multi-select, text, textarea, number), trigger the campaign initiation ritual animation, have my choices persisted to PostgreSQL and the memory layer via `POST /v1/playthroughs`, and seamlessly navigate to `/play/:playthrough_id` to start my journey.
- **Success Criteria:**
  - `/setup/:id` dynamically fetches scenario data and `setup_schema` from Core API.
  - Submitting setup values validates against `setup_schema` and sends a `POST /v1/playthroughs` request with `dict[str, object]` payload.
  - Unauthenticated users attempting to open or submit setup are redirected to `/login`.
  - `DramaticSetupLoader` handles loading states smoothly and gracefully closes with error toast if API fails.
  - On API success + loader completion, player is routed to `/play/:playthrough_id`, where `usePlaythrough` loads live playthrough state.

## 2. Technical Architecture & Data Flow
- **Components Involved:**
  - **Core API (`apps/core-api`)**: FastAPI `POST /v1/playthroughs` and `GET /v1/playthroughs/{id}` endpoints, `PlaythroughService`, `PlaythroughCreate` schema, and `_validate_setup_values` handler.
  - **Frontend (`apps/frontend`)**:
    - Routing: `/setup/:id` (`SetupPage.tsx`), `/play/:id` (`PlayPage.tsx`).
    - Components: `SetupStageCard.tsx`, `DramaticSetupLoader.tsx`.
    - API Client & Hooks: `playthroughs.api.ts`, `useSetup.ts`, `usePlaythrough.ts`, `useScenarioFocus.ts`.
    - Client Store: `usePlayStore` (Zustand).

- **Sequence Flow:**
  1. Player navigates to `/setup/:id`. `SetupPage` checks auth state (redirects to `/login` if null) and fetches scenario details via `useScenarioFocus(id)`.
  2. Player populates setup input fields and clicks **"Embark on Journey"**.
  3. `SetupStageCard` validates local form requirements and passes `setup_values` (`Record<string, unknown>`) to `SetupPage`.
  4. `SetupPage` sets `is_loading = true` (displaying `DramaticSetupLoader`) and fires `useCreatePlaythrough()` mutation.
  5. `POST /v1/playthroughs` validates `setup_values` against `scenario.setup_schema`, snapshots scenario state, clones memory space template, persists entity to DB, and returns `PlaythroughResponse`.
  6. Upon completion of both the backend request and the dramatic loading animation, `SetupPage` navigates to `/play/:playthrough_id`.
  7. If backend fails, `DramaticSetupLoader` closes and an error toast notification is displayed.

---

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- **Core API Lint & Format:**
  `cd apps/core-api && ruff check . --fix && ruff format .`
- **Core API Tests:**
  `cd apps/core-api && pytest tests/services/test_playthrough_service.py tests/routers/test_playthrough_router.py`
- **Frontend Type-Check & Build:**
  `cd apps/frontend && npx tsc --noEmit && npm run build`
- **Frontend Lint & Format:**
  `cd apps/frontend && npx prettier --write . && npx eslint . --fix`

### 3.2. Testing Strategy & Conformance
- **Backend Service & Router Unit/Integration Tests (`pytest`):**
  - **Happy Path:** Create a playthrough with diverse input types (single select string, multi-select list, text, number) in `setup_values`. Verify `Playthrough` entity and `Participant` record persist cleanly in PostgreSQL.
  - **Validation Errors:** Test missing required setup fields and invalid single-select choices. Verify `InvalidSetupValuesError` is thrown and returns HTTP 400 Bad Request.
  - **Memory Space Clone:** Verify `_clone_memory_space` is called with correct `scenario_id` and `playthrough_id`.
- **Frontend Type Safety & Linting:**
  - Run `npx tsc --noEmit` to ensure zero type errors across all updated API functions, hooks, and page components.
  - Run `npx prettier --write .` and `npx eslint . --fix`.
- **End-to-End Browser Verification (`browser_subagent`):**
  - Verify guest user redirect to `/login?redirect=/setup/:id`.
  - Simulate player completing dynamic setup fields and clicking **"Embark on Journey"**.
  - Verify `DramaticSetupLoader` overlay renders ritual state transitions.
  - Confirm successful POST request to `/v1/playthroughs` and automatic navigation to `/play/:playthrough_id`.
  - Verify error recovery: simulate API failure, verify loader closes and error toast is displayed.

### 3.3. Project Structure & File Layout
- **Files to Modify:**
  - `apps/core-api/app/models/playthrough.py` (Update `PlaythroughCreate.setup_values` type to `dict[str, object]`)
  - `apps/core-api/app/services/playthrough_service.py` (Update `_validate_setup_values` for flexible object values)
  - `apps/frontend/src/features/play/api/playthroughs.api.ts` (Implement API endpoints `createPlaythrough` and `getPlaythrough`)
  - `apps/frontend/src/features/play/hooks/useSetup.ts` (Implement `useCreatePlaythrough` mutation and setup hooks)
  - `apps/frontend/src/features/play/hooks/usePlaythrough.ts` (Implement `usePlaythrough` query hook)
  - `apps/frontend/src/features/play/pages/SetupPage.tsx` (Wire live scenario query, auth check, API mutation, loader, error toast)
  - `apps/frontend/src/features/play/components/SetupScreen/SetupStageCard.tsx` (Pass typed `setup_values` dict to parent handler)
  - `apps/frontend/src/features/play/pages/PlayPage.tsx` (Wire `usePlaythrough(id)` to initialize playthrough session)

### 3.4. Code Style & Interfaces
```typescript
// apps/frontend/src/features/play/api/playthroughs.api.ts
export interface CreatePlaythroughPayload {
  scenario_id: string;
  setup_values: Record<string, unknown>;
}

export interface PlaythroughResponse {
  playthrough_id: string;
  scenario_id: string;
  scenario_title: str;
  created_by: string;
  state: Record<string, unknown>;
  checkpoint?: string | null;
  turn_count: number;
  status: string;
  scenario_version: number;
  scenario_snapshot: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export async function createPlaythrough(
  payload: CreatePlaythroughPayload,
): Promise<PlaythroughResponse> {
  const { data } = await apiClient.post<PlaythroughResponse>(
    "/v1/playthroughs",
    payload,
  );
  return data;
}
```

```python
# apps/core-api/app/models/playthrough.py
class PlaythroughCreate(BaseModel):
    """Payload to start a new playthrough of a published scenario."""

    scenario_id: uuid.UUID
    setup_values: dict[str, object] = Field(default_factory=dict)
```

### 3.5. Git & Review Workflow
- Branch name: `feat/functional-setup-page`
- Verification checklist:
  - Backend pytest passes for playthrough creation with diverse input types.
  - Frontend typecheck (`tsc --noEmit`) passes with strict types.
  - Unauthenticated access cleanly redirects to `/login`.
  - API failure displays error toast and hides loader.

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** Require user auth before `POST /v1/playthroughs`; maintain max 30 lines per function and max 2 nesting levels; run linters.
- ⚠️ **Ask First:** Schema modifications to persistent database columns (none required for this spec).
- 🚫 **Never:** Use raw `any` types; perform synchronous I/O; swallow API errors silently.

---

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Network Failure / Server Error during Creation:** Loader is cancelled immediately, error message displayed via toast/alert, user remains on setup form without losing filled values.
- **Scenario Archived / Draft State:** If a scenario is no longer published, backend returns `404` or `400` `ScenarioNotPublishedError`, which displays an appropriate error state on setup page.
- **Missing Auth Token:** Handled client-side before submission by redirecting unauthenticated users to `/login?redirect=/setup/:id`.

---

## 5. Phased Implementation Tasks (Task Checklist)

- [ ] **Task 1 (Core API Pydantic & Service Updates):** Update `PlaythroughCreate.setup_values` type to `dict[str, object]`, adapt `_validate_setup_values` in `playthrough_service.py`, and update pytest test cases.
- [ ] **Task 2 (Frontend Playthrough API Client & Hooks):** Implement `playthroughs.api.ts`, `useSetup.ts` (`useCreatePlaythrough`), and `usePlaythrough.ts`.
- [ ] **Task 3 (Setup Page Integration & Auth Protection):** Wire `SetupPage.tsx` and `SetupStageCard.tsx` with live scenario fetching, auth check redirection, `useCreatePlaythrough` mutation, loader sequence, and error toasts.
- [ ] **Task 4 (Play Page Initialization):** Wire `PlayPage.tsx` with `usePlaythrough(id)` to load active playthrough state into `usePlayStore`.
