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

## 4. SQLAlchemy does not auto-order cross-table INSERTs for plain FK-only models
- **What:** SQLAlchemy did not auto-order cross-table INSERTs by FK dependency for plain (non-`relationship()`) mapped models — reproduced directly against `aidnd_test_db` while seeding TRS integration test fixtures (`apps/turn-resolution-service/tests/`), where inserting a `User` and a `Scenario` together in a single `session.add_all([...]); await session.flush()` call raised a `ForeignKeyViolationError` because the child row was emitted before its parent.
- **Why:** TRS's ORM models (`app/db/models/`) mirror core-api's schema but declare no `relationship()` links between entities, only raw FK columns — SQLAlchemy's unit-of-work insert ordering leans on `relationship()`-derived dependency processors, so plain FK columns alone aren't enough for it to sequence multi-table inserts correctly within one flush.
- **Where:** Worked around locally in TRS's test seed helpers (`apps/turn-resolution-service/tests/repositories/*.py`, `apps/turn-resolution-service/tests/turn/test_pipeline.py`) by flushing parent rows before dependent ones, one entity at a time. Not yet an issue in production code paths (state_writer.py's writes are single-table `update`/`create` calls), but worth keeping in mind for any future TRS (or core-api) code that batches multi-table inserts in one `flush()`.
- **How:** Either keep flushing parent-before-child explicitly wherever multi-table inserts happen in one transaction, or add `relationship()` declarations between the mirrored models so SQLAlchemy's automatic dependency sort can be relied on instead.










Note:- while stress-testing the new endpoint with back-to-back curl calls, I found the existing get_db_session dependency pattern (commit-after-response, used by every mutating endpoint in core-api, not just mine) has a narrow eventual-consistency window — an immediate GET right after a write can occasionally see the pre-write value for a fraction of a second. It's pre-existing and doesn't affect the actual feature (the frontend updates its cache directly from the PATCH response, it never re-fetches), but it's a latent architectural note if you ever want fully linearizable reads after writes.

I didn't do a real browser/screenshot pass — no browser automation tool was available in this environment and standing up full Firebase auth + TRS for a visual check was out of scope for the fix itself. If you want that, let me know and I can look at wiring up Playwright against the dev server.