# Spec: Scenario Creation Newbie Mode Frontend

## 1. Objective & User Outcome
- **Problem Statement:** AI-DND currently supports complex, structured scenario creation (Master Mode). Newbie creators need an intuitive, distraction-free authoring experience that allows them to define a scenario using freeform text (lore, premise) without managing structured game state manually.
- **User Story:** As a creator, I want to use a sleek, guided step-by-step editor with built-in AI assistance so that I can easily write and publish a rich world lore scenario in a modern, immersive environment.
- **Success Criteria:** 
  - A seamless 4-step creation wizard without page reloads.
  - A distraction-free markdown editor (IBM Plex Mono, dark aesthetic) for lore and prompts.
  - Visual AI chat assistant UI implemented (functionality out of scope).
  - Auto-save functionality with faint "saved" UI indicators.
  - Ability to toggle between Newbie and Master modes at the top of the creation page.
  - Extracted data is editable in the final review step.

## 2. Technical Architecture & Data Flow
- **Components Involved:** 
  - `CreateScenarioPage` (Frontend container managing mode toggle and wizard state).
  - Wizard Steps: `Step1Meta`, `Step2Lore`, `Step3Narrator`, `Step4Review`.
  - Shared UI: Distraction-free markdown editor, AI Chat sidebar UI.
  - Zustand Store (`studio.store.ts`): Manages draft state and active wizard step.
- **Sequence Flow:** 
  1. User navigates to `/studio/new`. `CreateScenarioPage` mounts.
  2. User selects "Newbie" mode via a top toggle switch.
  3. User progresses through 4 seamless steps, with local state syncing to a Zustand store.
  4. Auto-save triggers debounced `PATCH` requests to the backend (mocked for now).
  5. Step 4 displays extracted entities/facts (mocked), allowing inline edits.
  6. Final "Publish" action is triggered.

## 3. The Six Core Engineering Dimensions
### 3.1. Commands
- Build: `npm run build`
- Test: `npm run test`
- Lint / Type-Check: `prettier --write . && eslint . --fix`

### 3.2. Testing Strategy & Conformance
- Test framework: React Testing Library.
- Strategy: Test the wizard step progression (Next/Back). Test the mode toggle state. Test that auto-save indicators appear upon typing in the distraction-free editor.

### 3.3. Project Structure & File Layout
- Files to create:
  - `apps/frontend/src/features/studio/pages/CreateScenarioPage.tsx` (Central hub)
  - `apps/frontend/src/features/studio/components/NewbieWizard/`
    - `WizardContainer.tsx`
    - `Step1Meta.tsx`
    - `Step2Lore.tsx`
    - `Step3Narrator.tsx`
    - `Step4Review.tsx`
  - `apps/frontend/src/features/studio/components/AIChatSidebar/AIChatSidebar.tsx`
  - `apps/frontend/src/features/studio/components/MarkdownEditor/DistractionFreeEditor.tsx`
- Files to modify:
  - `apps/frontend/src/app/router.tsx` (Update route for creating scenarios)
  - `apps/frontend/src/features/studio/stores/studio.store.ts` (Add wizard state)

### 3.4. Code Style & Interfaces
- State interfaces will be added to `scenario.types.ts`.
- Component definitions will enforce single responsibility (one component per file) and utilize existing Tailwind variables for dark mode and IBM Plex Mono fonts.

### 3.5. Git & Review Workflow
- Suggested branch name: `feat/newbie-mode-frontend`
- Commit scope: Follow conventional commits (`feat(studio): add newbie wizard steps`).

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** Enforce strict type safety; use early returns in React components; ensure styling relies purely on Tailwind utilities.
- ⚠️ **Ask First:** Modifying the shared `Scenario` API types.
- 🚫 **Never:** Introduce inline styles; mix Master mode and Newbie mode UI components in the same render tree without explicit boundaries.

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Network loss during auto-save:** The faint "saved" text should switch to an "unsaved changes" warning.
- **Large Lore Inputs:** Markdown editor must efficiently render large bodies of text without lagging.
- **Mode Switching:** If a user writes Newbie lore and switches to Master mode, we need a clear warning modal that unstructured lore may not seamlessly translate to structured Master mode entities.

## 5. Phased Implementation Tasks (Task Checklist)
- [ ] **Task 1 (Routing & Container):** Implement `CreateScenarioPage.tsx` with the Newbie/Master toggle and setup Zustand store for wizard step tracking.
- [ ] **Task 2 (Wizard Step 1 & 3):** Implement `Step1Meta.tsx` (Metadata) and `Step3Narrator.tsx` (AI Instructions/Style notes).
- [ ] **Task 3 (Lore Editor & AI Chat):** Implement `Step2Lore.tsx` featuring the distraction-free `MarkdownEditor` (with IBM Plex Mono) and the `AIChatSidebar` UI. Add the multiple prompt structure vs. single dump toggle.
- [ ] **Task 4 (Review & Auto-save):** Implement `Step4Review.tsx` with mock extracted data editing. Wire up the debounced auto-save UI logic ("saved" indicator) across all steps.
