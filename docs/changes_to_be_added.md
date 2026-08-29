# Backend & Data Model Changes To Be Added

## 1. Add `logline` to `Scenario`
- **What:** Add a short descriptive text field (`logline` or `short_description`) to the core Scenario model.
- **Why:** The new landing page card design requires a quick hook to display on hover, distinct from the full description shown on the detail page.
- **Where:** 
  - Backend: `apps/core-api/app/models/scenario.py` (SQLAlchemy model), Pydantic schemas, and Alembic migrations.
  - Frontend: `apps/frontend/src/features/play/types/scenario.ts`.
- **How:** Add a string column (e.g., `String(150)` limit), update the CRUD creation endpoints to accept it, and map it in the frontend TypeScript interface.

## 2. Add `genre` strict typing and mapping
- **What:** Ensure `genre` is consistently typed and available across all scenarios.
- **Why:** The frontend will use the `genre` field to dynamically apply accent colors and motif treatments to the UI shell and cards.
- **Where:** 
  - Backend: Pydantic schemas to validate against an Enum of supported genres (High Fantasy, Sci-Fi, Noir, etc.).
  - Frontend: `apps/frontend/src/features/play/types/scenario.ts` and UI configuration constants.
- **How:** Define a `ScenarioGenre` Enum in Python, update database constraints if necessary, and create a centralized color mapping object in the frontend (e.g. `const GENRE_COLORS: Record<ScenarioGenre, string> = {...}`).

## 3. Install Framer Motion
- **What:** Add `framer-motion` as a frontend dependency.
- **Why:** Required for complex staggered scroll/mount reveals on dynamic content and page-level route transitions that feel like "entering a scene".
- **Where:** `apps/frontend/package.json`
- **How:** Run `npm install framer-motion` (or equivalent) in the `apps/frontend` directory.
