# Spec: Scenario Focus Page & Backend Extensions

## 1. Objective & User Outcome
- **Problem Statement:** Players discovering scenarios on the Landing Page or Discovery Page currently lack a dedicated, immersive overview page to read full lore, inspect setup requirements, see community reviews, bookmark, or start playing.
- **User Story:** As a player, I want to click on a scenario card to land on `/scenario/:id`, view its banner, lore, setup preview, rating/reviews, and public playthroughs, so that I can decide whether to play it or bookmark it for later.
- **Success Criteria:** 
  - Clicking any scenario card navigates to `/scenario/:id` (with back button returning to origin).
  - Explicit "Play" button on cards still navigates straight to `/setup/:id`.
  - `/scenario/:id` renders as a single-page continuous scroll with high-fantasy UI, displaying creator info, lore, setup preview, age advisory tag, estimated playtime, ratings/reviews, and public playthrough list.
  - Creator of the scenario sees an "Edit in Studio" CTA directing to `/studio/:id`.
  - Rating/review submission is restricted to users with >= 10 turns on a playthrough for that scenario.
  - Bookmarking syncs to backend when authenticated and mirrors to `localStorage`.

---

## 2. Technical Architecture & Data Flow
```
[Landing / Discovery Feed]
       │
       ├─► Click Card ──► Navigate to `/scenario/:id` (ScenarioFocusPage)
       └─► Click Play ──► Navigate to `/setup/:id` (SetupPage)

[ScenarioFocusPage]
       ├── GET /v1/scenarios/{id} (includes creator info, is_bookmarked, world_data, setup_schema)
       ├── GET /v1/scenarios/{id}/reviews (list community ratings & comments)
       ├── GET /v1/scenarios/{id}/playthroughs (list public playthrough summaries)
       ├── POST /v1/scenarios/{id}/bookmark (toggle bookmark status)
       └── POST /v1/scenarios/{id}/reviews (submit rating/review after >= 10 turns validation)
```

---

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- Frontend Dev / Build: `cd apps/frontend && npm run build`
- Frontend Type Check: `cd apps/frontend && npx tsc --noEmit`
- Frontend Lint: `cd apps/frontend && npm run lint`
- Backend Formatting & Linting: `cd apps/core-api && ruff format . && ruff check .`
- Backend Tests: `cd apps/core-api && pytest`

### 3.2. Testing Strategy & Conformance
- **Backend Tests:**
  - `tests/routers/test_scenario_focus.py`: Test `GET /v1/scenarios/{id}`, `POST/DELETE bookmark`, `GET/POST reviews` (with <10 turns vs >=10 turns validation check).
- **Frontend Validation:**
  - Validate clean route loading, `navigate(-1)` back action, conditional rendering of "Edit in Studio", bookmark toggle with local fallback, and review form submission.

### 3.3. Project Structure & File Layout
**Files to create:**
- Backend:
  - `apps/core-api/app/db/models/bookmark.py` (User bookmark entity)
  - `apps/core-api/app/db/models/review.py` (Scenario review & rating entity)
  - `apps/core-api/app/routers/ratings.py` (Scenario rating & review endpoints)
  - `apps/core-api/tests/routers/test_scenario_focus.py` (Integration tests)
- Frontend:
  - `apps/frontend/src/features/play/pages/ScenarioFocusPage.tsx`
  - `apps/frontend/src/features/play/components/ScenarioFocus/ScenarioBannerHero.tsx`
  - `apps/frontend/src/features/play/components/ScenarioFocus/ScenarioLoreSection.tsx`
  - `apps/frontend/src/features/play/components/ScenarioFocus/ScenarioSetupPreview.tsx`
  - `apps/frontend/src/features/play/components/ScenarioFocus/ScenarioReviewsSection.tsx`
  - `apps/frontend/src/features/play/components/ScenarioFocus/ScenarioPublicPlaythroughs.tsx`
  - `apps/frontend/src/features/play/hooks/useScenarioFocus.ts`
  - `apps/frontend/src/features/play/api/scenarioFocus.api.ts`

**Files to modify:**
- Backend:
  - `apps/core-api/app/db/models/__init__.py`
  - `apps/core-api/app/db/models/scenario.py`
  - `apps/core-api/app/models/scenario.py`
  - `apps/core-api/app/routers/scenarios.py`
  - `apps/core-api/app/services/scenario_service.py`
  - `apps/core-api/app/repositories/scenario_repo.py`
- Frontend:
  - `apps/frontend/src/app/router.tsx`
  - `apps/frontend/src/features/play/components/DiscoveryFeed/ScenarioCard.tsx`
  - `apps/frontend/src/features/play/components/DiscoveryFeed/WideScenarioCard.tsx`
  - `apps/frontend/src/features/landing/components/ScenarioCarousel.tsx`

### 3.4. Code Style & Interfaces

#### Pydantic Schema: `ScenarioReviewCreate` & `ScenarioReviewResponse`
```python
class ScenarioReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)

class ScenarioReviewResponse(BaseModel):
    review_id: uuid.UUID
    scenario_id: uuid.UUID
    user_id: uuid.UUID
    user_display_name: str
    rating: int
    comment: str | None
    created_at: datetime
```

#### TypeScript Types: `ScenarioFocusDetail`
```typescript
export interface ScenarioFocusDetail extends DisplayScenario {
  fullLore?: string;
  creatorDisplayName?: string;
  creatorAvatarUrl?: string;
  isBookmarked?: boolean;
  canReview?: boolean; // True if current user has played >= 10 turns
  setupSchema?: Array<{
    id: string;
    label: string;
    type: string;
    options?: string[];
  }>;
}
```

### 3.5. Git & Review Workflow
- Branch name: `feat/scenario-focus-page`
- PR checks: `ruff check` + `pytest` + `tsc --noEmit` + `eslint`.

### 3.6. Boundaries
- ✅ **Always:** Follow nesting < 3 levels and function length < 30 lines.
- ⚠️ **Ask First:** Database schema modifications/migrations.
- 🚫 **Never:** Skip authorization checks on review submission or edit button checks.

---

## 4. Edge Cases & Handling
- **Guest Users:** Can view `/scenario/:id`, read reviews, inspect setup preview, bookmark locally to `localStorage`. Review submission prompts auth login modal or toast.
- **Unpublished / Private Scenario:** Only creator can access if scenario is in `draft` status.

---

## 5. Phased Implementation Tasks
- [ ] **Task 1: Backend Database & Models** — Define `Bookmark` and `Review` ORM models and Pydantic schemas.
- [ ] **Task 2: Backend API Endpoints** — Add bookmark toggle, review listing/submission, and public playthroughs query in `core-api`.
- [ ] **Task 3: Integration Tests** — Write FastAPI integration tests for `/v1/scenarios/{id}` focus endpoints and reviews validation.
- [ ] **Task 4: Frontend API & Hooks** — Implement `scenarioFocus.api.ts` and `useScenarioFocus.ts` with React Query & localStorage fallback.
- [ ] **Task 5: Frontend ScenarioFocusPage Components** — Build `ScenarioFocusPage` and subcomponents (`ScenarioBannerHero`, `ScenarioLoreSection`, `ScenarioSetupPreview`, `ScenarioReviewsSection`, `ScenarioPublicPlaythroughs`).
- [ ] **Task 6: Card Navigation Integration** — Wire Scenario cards on Landing and Discovery pages to navigate to `/scenario/:id`.
- [ ] **Task 7: Verification** — Run full linter, typecheck, pytest, and visual verification.
