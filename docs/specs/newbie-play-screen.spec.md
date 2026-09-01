# Spec: Newbie Mode Play Screen

## 1. Objective & User Outcome
- **Problem Statement:** Players need an immersive, atmospheric, and highly functional gameplay surface to play text-based Newbie Mode scenarios. The screen must support a 3-column layout, seamless streaming AI narration, interactive action modes (`Say`, `Do`, `Story`, `See`), turn retries and action edits, collapsible world lore and character sheet sidebars, playthrough sharing, spectator mode, and session completion metrics.
- **User Story:** As a player in a Newbie Mode scenario, I want an atmospheric 3-column game view with background mist, subtle narrative history, flexible action mode pills, and collapsible sidebars for lore and character information so that I can comfortably immerse myself in the AI-driven narrative.
- **Success Criteria:**
  1. Full 3-column desktop layout with collapsible Left Sidebar (World Codex/Lore) and Right Sidebar (Character Sheet) with smooth transitions.
  2. Mobile-responsive toggle for sidebars (sliding drawers/modals).
  3. Continuous token streaming narrative feed with typewriter/fade effects and a working "Stop Generation" button.
  4. Floating glassmorphism action input bar with auto-expanding height, multi-mode pill toggle (`Say`, `Do`, `Story`, `See`), dynamic placeholders, and shortcut support (`Ctrl/Cmd + Enter` submit).
  5. Action retry & turn editing mechanics that load previous actions back into the input bar and replace turns in log state.
  6. Modals for Share Playthrough, Character Sheet Edit Warning, and End Playthrough (5-star rating, review, stats).
  7. Spectator Mode banner locking the input bar for read-only view.
  8. Interactive mock mode with simulated token streaming for standalone previewing.

---

## 2. Technical Architecture & Data Flow

### Components Architecture
```
PlayPage (Route Layer)
 ├── PlayHeader (Top Nav, Title, Turn Count, Save Indicator, Share/End Modals)
 ├── BackgroundMist (Canvas / GPU-accelerated animated particles overlay)
 └── PlayScreen (3-Column Shell)
      ├── WorldCodexSidebar (Left: Premise, Lore, Key Facts, Story Cards, Collapse Toggle)
      ├── MainNarrativeArea (Center)
      │    ├── OpeningSceneBlock (Creator Premise)
      │    ├── NarrativeFeed (Turn entries: Action + Narration, IM Fell English font)
      │    ├── StreamingNarrationBlock (Live streaming token feed + Stop button)
      │    ├── ScrollToBottomButton (Floating auto-scroll trigger)
      │    └── ActionInputBar (Floating glassmorphism box)
      │         ├── ActionModePillsToggle (Say, Do, Story, See)
      │         ├── AutoExpandingTextarea (Enter = newline, Cmd+Enter = submit)
      │         └── ActionSubmitControls (Submit / Retry / Stop buttons)
      └── CharacterSheetSidebar (Right: Player Setup Details, Edit Character + Warning, Collapse Toggle)
```

### Data & Action Sequence Flow
1. **Initial Load**:
   - `PlayPage` checks route params (`playthroughId`). Loads initial playthrough state or defaults to interactive mock state.
   - Narrative feed initializes with Creator Opening Premise at the top.
   - Input bar initializes with default mode (`Do`).
2. **Turn Submission**:
   - User selects mode (`Say`, `Do`, `Story`, `See`) and types action text.
   - On submit (`handleActionSubmit`), current mode becomes default for next turn.
   - Action entry is appended to turn history.
   - Simulated/SSE streaming begins (`is_narrating: true`). Output streams into `StreamingNarrationBlock`.
3. **Stream Completion / Stop**:
   - On complete, streaming text moves into turn log entry (`narration_text`), `is_narrating` becomes `false`.
   - On Stop (`handleStopGeneration`), streaming halts, and incomplete turn is deleted.
4. **Retry / Edit Turn**:
   - On Retry (`handleRetryTurn`): Re-runs streaming using the last action text.
   - On Edit Action (`handleEditLastAction`): Replaces input bar content with previous action text, deletes last turn from history log, allowing user to re-submit modified text.

---

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- **Build**: `npm run build --prefix apps/frontend`
- **Test**: `npm run test --prefix apps/frontend`
- **Lint / Type-Check**: `npx tsc --noEmit --project apps/frontend/tsconfig.json` && `npx eslint apps/frontend/src/features/play --ext .ts,.tsx`
- **Format**: `npx prettier --write apps/frontend/src/features/play`

### 3.2. Testing Strategy & Conformance
- Component unit & interaction tests with React Testing Library:
  - `apps/frontend/src/features/play/components/PlayScreen/__tests__/ActionInput.test.tsx`: Tests mode pill selection, shortcut submission, auto-expanding textarea.
  - `apps/frontend/src/features/play/components/PlayScreen/__tests__/PlayScreen.test.tsx`: Tests 3-column layout collapse toggles, sidebar responsiveness, and spectator banner.
  - `apps/frontend/src/features/play/components/PlayScreen/__tests__/NarrationStream.test.tsx`: Tests continuous token rendering, stop button execution, and auto-scroll behavior.

### 3.3. Project Structure & File Layout

#### Files to Create / Implement:
- `apps/frontend/src/features/play/types/play.types.ts`
- `apps/frontend/src/features/play/stores/play.store.ts`
- `apps/frontend/src/features/play/components/PlayScreen/BackgroundMist.tsx`
- `apps/frontend/src/features/play/components/PlayScreen/PlayHeader.tsx`
- `apps/frontend/src/features/play/components/PlayScreen/WorldCodexSidebar.tsx`
- `apps/frontend/src/features/play/components/PlayScreen/CharacterSheetSidebar.tsx`
- `apps/frontend/src/features/play/components/PlayScreen/ActionModePills.tsx`
- `apps/frontend/src/features/play/components/PlayScreen/ActionInput.tsx`
- `apps/frontend/src/features/play/components/PlayScreen/NarrationStream.tsx`
- `apps/frontend/src/features/play/components/PlayScreen/TurnHistory/TurnEntry.tsx`
- `apps/frontend/src/features/play/components/PlayScreen/TurnHistory/TurnHistory.tsx`
- `apps/frontend/src/features/play/components/PlayScreen/Modals/SharePlaythroughModal.tsx`
- `apps/frontend/src/features/play/components/PlayScreen/Modals/EditCharacterWarningModal.tsx`
- `apps/frontend/src/features/play/components/PlayScreen/Modals/EndPlaythroughModal.tsx`
- `apps/frontend/src/features/play/components/PlayScreen/PlayScreen.tsx`
- `apps/frontend/src/features/play/pages/PlayPage.tsx`
- `apps/frontend/src/features/play/mock/playthroughMock.ts`

### 3.4. Code Style & Interfaces

#### TypeScript Contracts (`apps/frontend/src/features/play/types/play.types.ts`)
```typescript
export type ActionMode = 'say' | 'do' | 'story' | 'see';

export interface TurnLogItem {
  id: string;
  turn_number: number;
  action_mode: ActionMode;
  action_text: string;
  narration_text: string;
  created_at: string;
}

export interface CharacterSetupField {
  key: string;
  label: string;
  value: string;
}

export interface PlaythroughState {
  playthrough_id: string;
  scenario_id: string;
  scenario_title: string;
  creator_name: string;
  cover_image_url?: string;
  opening_premise: string;
  world_lore: string;
  key_facts: string[];
  character_name: string;
  custom_fields: CharacterSetupField[];
  turns: TurnLogItem[];
  is_spectator: boolean;
  is_narrating: boolean;
  active_mode: ActionMode;
  streaming_text: string;
  is_left_sidebar_open: boolean;
  is_right_sidebar_open: boolean;
}
```

### 3.5. Git & Review Workflow
- Branch name: `feat/newbie-play-screen`
- Commit format: `feat(play): implement newbie mode 3-column play screen`

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** Use `IM Fell English` for narrative blocks and `IBM Plex Mono` for UI controls & tags; enforce max 2 levels of nesting; enforce under 30 lines per function.
- ⚠️ **Ask First:** Changing route paths in `router.tsx` or modifying shared Tailwind font utilities.
- 🚫 **Never:** Hardcode backend API secrets; use raw inline CSS styles; duplicate shared UI components.

---

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Network / Stream Interruption:** If simulated or live SSE stream drops, state retains last completed turn and shows a retry notification.
- **Empty Action Submit:** Input submit button disabled when textarea contains only whitespace.
- **Large Screen vs Small Mobile View:** Sidebars automatically convert to full-screen drawers on viewports under `1024px` (`lg` breakpoint).
- **Long Turn History Scroll Performance:** Virtualized / efficient DOM rendering for narrative blocks to maintain smooth 60fps scrolling.

---

## 5. Phased Implementation Tasks

- [ ] **Task 1 (Types & Mock Data Layer):** Define contracts in `play.types.ts` and create `playthroughMock.ts` with rich fantasy scenario data and mock token streamer.
- [ ] **Task 2 (Zustand Store):** Create flat `play.store.ts` handling active mode, sidebar visibility, turn log mutation, stream state, and edit/retry actions.
- [ ] **Task 3 (Sub-Components & Sidebars):**
  - Implement `BackgroundMist.tsx` for ambient particle motion.
  - Implement `WorldCodexSidebar.tsx` (Left panel with premise, lore cards, collapse button).
  - Implement `CharacterSheetSidebar.tsx` (Right panel with editable fields + warning modal trigger).
- [ ] **Task 4 (Narrative & Action Input Components):**
  - Implement `ActionModePills.tsx` (Say, Do, Story, See selection pill).
  - Implement `ActionInput.tsx` (Floating glassmorphism box, auto-expanding textarea, submit/stop buttons).
  - Implement `TurnEntry.tsx` & `NarrationStream.tsx` (IM Fell English text, retry/edit buttons, typing effect).
  - Implement `TurnHistory.tsx` with auto-scroll and floating "Scroll to bottom" button.
- [ ] **Task 5 (Header & Modals):**
  - Implement `PlayHeader.tsx` (Title, turn count, auto-save status, mobile drawers triggers).
  - Implement `SharePlaythroughModal.tsx`, `EditCharacterWarningModal.tsx`, and `EndPlaythroughModal.tsx`.
- [ ] **Task 6 (Assembly & Page Route Integration):** Assemble complete 3-column `PlayScreen.tsx` and integrate into `PlayPage.tsx` under `/play/:id`.
- [ ] **Task 7 (Verification & Format):** Run `prettier`, `eslint`, and `tsc` type-checks to verify zero errors or warnings.
