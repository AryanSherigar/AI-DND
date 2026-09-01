# Spec: Newbie Mode Player Setup & Custom Inputs

## 1. Objective & User Outcome
- **Problem Statement:** Creators building scenarios in Newbie Mode need a way to let players customize their experience (e.g. choose starting factions, character background, equipment, name, difficulty) prior to starting Turn 1.
- **User Story:** As a scenario creator, I want to configure interactive player setup fields (dropdowns, checkboxes, text fields, numbers) in the Newbie Studio so that players can customize their starting choices when initiating a playthrough, which are then passed to the AI Narrator.
- **Success Criteria:**
  - Scenario creators can add, configure, reorder, and remove custom input fields in a dedicated "Player Setup" section in Studio.
  - Creators can preview the interactive setup form directly within the Studio layout.
  - When starting a playthrough, players are presented with a Playthrough Setup Modal matching the creator's defined fields.
  - Player choices are validated, stored in playthrough state, and appended to the Turn 1 opening prompt for Gemini.

## 2. Technical Architecture & Data Flow
- **Components & Layout:**
  - `StudioDocumentLayout.tsx`: Updated table of contents to insert `#setup` ("Player Setup") between `#lore` and `#narrator`.
  - `StepPlayerSetup.tsx`: New step component in `apps/frontend/src/features/studio/components/NewbieWizard/`.
  - `PlaythroughSetupModal.tsx`: Modal component in `apps/frontend/src/features/play/components/`.
  - `studio.store.ts`: State management for `SetupInputField[]` in `NewbieDraft`.
- **Sequence Flow:**
  1. **Studio Creation:** Creator builds scenario metadata, lore, and configures setup fields (`single_select`, `multi_select`, `text`, `textarea`, `number`) with labels, options, required flags, defaults, and helper texts.
  2. **Storage:** `setup_schema` is saved as JSONB in `scenarios.setup_schema`.
  3. **Playthrough Launch:** Player clicks "Start Playthrough". If `setup_schema` is present, `PlaythroughSetupModal` opens.
  4. **Player Submission:** Player fills out setup choices; validation ensures required fields are populated.
  5. **Turn 1 Narration:** Player choices are formatted as structured markdown (`[PLAYER CHARACTER SETUP]`) and appended to `opening_prompt` sent to Gemini for Turn 1 streaming narration.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- Build: `npm run build` (in `apps/frontend`)
- Test: `npm run test`
- Type-check / Lint: `prettier --write . && eslint . --fix`

### 3.2. Testing Strategy & Conformance
- Component unit tests for `StepPlayerSetup.tsx` (adding, editing, reordering fields, option creation).
- Component unit tests for `PlaythroughSetupModal.tsx` (rendering fields based on `setup_schema`, required field validation, output payload generation).

### 3.3. Project Structure & File Layout
- **Files to create:**
  - `apps/frontend/src/features/studio/components/NewbieWizard/StepPlayerSetup.tsx`
  - `apps/frontend/src/features/play/components/PlaythroughSetupModal.tsx`
  - `docs/specs/newbie-mode-player-setup.spec.md`
- **Files to modify:**
  - `apps/frontend/src/features/studio/stores/studio.store.ts`
  - `apps/frontend/src/features/studio/components/StudioDocumentLayout.tsx`
  - `apps/frontend/src/features/play/types/scenario.ts`

### 3.4. Code Style & Interfaces
```typescript
export type SetupInputType = "single_select" | "multi_select" | "text" | "textarea" | "number";

export interface SetupInputOption {
  id: string;
  label: string;
  value: string;
}

export interface SetupInputField {
  id: string;
  key: string;
  label: string;
  type: SetupInputType;
  description?: string;
  placeholder?: string;
  required: boolean;
  options: SetupInputOption[];
  defaultValue?: string | string[] | number;
}
```

### 3.5. Git & Review Workflow
- Suggested branch name: `feat/newbie-player-setup`
- Commit scope guidelines: `feat(studio): add player setup fields step to newbie mode`

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** Keep components under 30 lines where possible or cleanly extracted; enforce max 2 nesting levels; use strict TypeScript.
- ⚠️ **Ask First:** Changing backend DB schemas beyond existing `setup_schema` column.
- 🚫 **Never:** Use inline styles; swallow validation errors silently.

## 4. Edge Cases & Graceful Degradation
- **Empty `setup_schema`:** If a scenario has no setup fields, `PlaythroughSetupModal` is skipped and game starts immediately.
- **Missing Required Fields:** Modal highlights missing required fields with clear warning states before proceeding.
- **Custom option deletion:** Deleting an option in Studio updates default value if it pointed to the deleted option.

## 5. Phased Implementation Tasks
- [ ] **Task 1 (Store & Types):** Extend `studio.store.ts` and scenario types with `SetupInputField` data models.
- [ ] **Task 2 (Studio Editor Step):** Implement `StepPlayerSetup.tsx` with interactive builder (add/remove fields, reorder, option management, required flag, helper text, preview toggle).
- [ ] **Task 3 (Document Layout Integration):** Wire `StepPlayerSetup` into `StudioDocumentLayout.tsx` TOC navigation.
- [ ] **Task 4 (Playthrough Setup Modal):** Implement `PlaythroughSetupModal.tsx` on the Play surface to collect player inputs and format choices for Turn 1 opening prompt.
