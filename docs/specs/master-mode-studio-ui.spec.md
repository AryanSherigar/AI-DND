# Spec: Master-Mode Studio Authoring UI

## 1. Objective & User Outcome

- **Problem Statement:** Every master-mode authoring component the README scaffolded (`EntityEditor`, `FactEditor`, `ConditionEditor`, `ExpressionBuilder` family, `StateSchemaEditor`, `EndConditionsEditor`) is a 0-byte stub, along with their API/hooks/types layers. `StudioDocumentLayout` — the only working authoring shell — is hardwired to the newbie-mode wizard steps. This spec builds the dense, structured, real-time-validated authoring surface master mode needs, backed by `master-mode-data-model.spec.md`'s endpoints.
- **User Story:** As a creator, I want a single authoring surface where I can define entities with their own attributes, connect them with facts (including secret ones), author active conditions and hard world-rule invariants, build a typed state schema, and set up win/lose outcomes — with broken references caught immediately, not at publish time — so I can build a large structured world with confidence that nothing I author is silently wrong.
- **Success Criteria:**
  - A new `MasterModeStudioLayout` (tabs/panels, not a linear wizard) replaces the newbie-only `StudioDocumentLayout` for `mode === "master"` scenarios, reusing the existing `AIChatSidebar` drawer pattern unmodified (advisory-only — it never writes structured data on the creator's behalf).
  - Every master-mode sub-resource (entities, facts, conditions, end conditions, invariants) has a working list + form UI wired to React Query hooks against the endpoints from `master-mode-data-model.spec.md`.
  - A single `ExpressionBuilder` component (not three separate implementations) is reused across `ConditionEditor` (active conditions + Effect C), `EndConditionsEditor`, and the new `InvariantEditor`.
  - Broken references (a fact pointing at a deleted entity, an expression referencing a state-schema field that doesn't exist) surface as inline errors as the creator types/selects, not only on save.
  - `StateSchemaEditor` supports every field shape from `master-mode-turn-pipeline.spec.md`'s validation model: primitives, entity refs, lists, nested objects, derived fields — and every field's `label` doubles as the terminology-relabeling mechanism (no separate feature needed).
  - Playtest mode, scenario duplication, setup archetypes, opening scene, narration font, and suggested action chips are all reachable from this surface.
  - `npx tsc --noEmit` and `eslint . --fix` clean; zero `any` types; every new hook file exports exactly one hook named after its resource, per CLAUDE.md.

## 2. Technical Architecture & Data Flow

- **Components Involved:** React + Vite feature `studio/`, React Query (server state), Zustand (`studio.store.ts`, extended for master-mode UI-only state — active tab, drawer state), `apiClient` (axios, existing), shadcn/ui primitives (`shared/components/ui/`).
- **Reference data:** every example is "The Hollow Cairn" (`docs/specs/master-mode-demo-scenario.md`).
- **Data flow (representative — creating a fact):** `FactEditor` form state → `useFacts().create(payload)` (React Query mutation) → `facts.api.ts`'s `createFact()` (axios POST to `/v1/scenarios/{id}/facts`) → on success, the entities/facts query cache invalidates → `FactEditor`'s reference-validity check (derived from the already-loaded `useEntities()` cache, no extra request) re-runs. Backend `422` domain errors (from `master-mode-data-model.spec.md`'s reference validation) surface as inline form errors via the same `extractErrorMessage` pattern `usePublish.ts` already uses.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands

- Type-check: `npx tsc --noEmit` (from `apps/frontend/`)
- Lint/Format: `npx prettier --write . && npx eslint . --fix`
- Test: `npx vitest run src/features/studio` (React Testing Library, per CLAUDE.md — no snapshot tests for these, they're all logic-bearing, not presentational leaves)
- Dev server (manual verification): `npm run dev`, then exercise the full "Hollow Cairn" authoring flow against a running Core API.

### 3.2. Testing Strategy & Conformance

- **Location:** colocated `*.test.tsx` next to each component, per existing repo convention (check `NewbieWizard` for the exact colocation pattern already in use, if any exists — otherwise `src/features/studio/components/**/__tests__/`).
- **Mocking:** `msw` intercepts `apiClient` calls at the network level, per CLAUDE.md — never mock React Query internals directly.
- **Required cases:**
  - `EntityEditor`: creating an entity with `entity_type: "item"` shows the `obtainable` toggle; other types don't (UI-level conditional, not a backend concern).
  - `FactEditor`: selecting a `subject` and toggling object-type between "entity" and "literal" clears the other field; submitting with neither set is blocked client-side before the request fires.
  - `FactEditor`: a fact referencing an entity that gets deleted in another tab (cache invalidation from `useEntities`) shows an inline "this entity no longer exists" warning without a page reload.
  - `ExpressionBuilder`: building `{ field: "player.health", op: "<=", value: 0 }` via `FieldPicker`/`OperatorPicker`/`ValueInput` produces the exact expression shape the backend expects (assert the serialized JSON, not just UI state).
  - `ExpressionBuilder`: `FieldPicker` lists both `state_schema` fields (dot-path, e.g. `player.health`) and entity attribute fields (e.g. `the_warden.health`), sourced from `useScenario()` + `useEntities()`, not hardcoded.
  - `StateSchemaEditor`: adding a nested `object` field, then a primitive field inside it, produces the exact nested `state_schema` shape from the demo scenario's `player` field.
  - `EndConditionsEditor`: drag-reordering two conditions updates their `priority` values via a batch `PATCH`, and the list re-renders in the new order optimistically (React Query `onMutate`).
  - Real-time validation: typing an `ExpressionBuilder` field path that doesn't exist in `state_schema`/entity attributes shows an inline error immediately (client-side check against already-loaded schema data — no round-trip needed for this specific check, unlike the entity/fact reference checks which do need the backend's `422`).
  - Playtest mode: clicking "Playtest" from a draft master-mode scenario calls the new playtest endpoint and navigates to the Play surface's existing play route with the returned `playthrough_id` — reuses the Play feature's existing routing, doesn't duplicate it.

### 3.3. Project Structure & File Layout

**Files to fill in (currently 0-byte stubs):**
- `apps/frontend/src/features/studio/api/{entities,facts,conditions}.api.ts`
- `apps/frontend/src/features/studio/hooks/{useEntities,useFacts,useConditions,useScenario}.ts`
- `apps/frontend/src/features/studio/types/{entity,fact,condition,scenario}.types.ts`
- `apps/frontend/src/features/studio/components/EntityEditor/{EntityEditor.tsx,EntityEditor.types.ts}`
- `apps/frontend/src/features/studio/components/FactEditor/{FactEditor.tsx,FactEditor.types.ts}`
- `apps/frontend/src/features/studio/components/ConditionEditor/{ConditionEditor.tsx,ConditionEditor.types.ts}`
- `apps/frontend/src/features/studio/components/ConditionEditor/ExpressionBuilder/{ExpressionBuilder,FieldPicker,OperatorPicker,ValueInput}.tsx`
- `apps/frontend/src/features/studio/components/StateSchemaEditor/StateSchemaEditor.tsx`
- `apps/frontend/src/features/studio/components/EndConditionsEditor/EndConditionsEditor.tsx`
- `apps/frontend/src/features/studio/components/SetupSchemaEditor/SetupSchemaEditor.tsx` (extended for setup archetypes, §3.4)
- `apps/frontend/src/features/studio/components/NarratorPersonaEditor/NarratorPersonaEditor.tsx` (extended for checkpoint-based persona overrides)
- `apps/frontend/src/features/studio/components/ScenarioMetaForm/ScenarioMetaForm.tsx`
- `apps/frontend/src/features/studio/pages/{StudioPage,EditScenarioPage}.tsx`

**Files to create (new):**
- `apps/frontend/src/features/studio/components/Layout/MasterModeStudioLayout.tsx` — the tabs/panels shell (§3.4).
- `apps/frontend/src/features/studio/components/InvariantEditor/{InvariantEditor.tsx,InvariantEditor.types.ts}`
- `apps/frontend/src/features/studio/components/RulesEditor/RulesEditor.tsx` — house rules markdown textarea (reuses `MarkdownEditor/DistractionFreeEditor.tsx`), bound to `Scenario.rules.text`.
- `apps/frontend/src/features/studio/components/EntityEditor/AttributesSchemaEditor.tsx` — per-entity typed attribute builder (a smaller sibling of `StateSchemaEditor`, same field-shape vocabulary, scoped to one entity).
- `apps/frontend/src/features/studio/components/OpeningSceneEditor/OpeningSceneEditor.tsx`
- `apps/frontend/src/features/studio/components/ActionChipsEditor/ActionChipsEditor.tsx`
- `apps/frontend/src/features/studio/components/NarrationFontPicker/NarrationFontPicker.tsx`
- `apps/frontend/src/features/studio/components/PlaytestButton/PlaytestButton.tsx`
- `apps/frontend/src/features/studio/components/DuplicateScenarioButton/DuplicateScenarioButton.tsx`
- `apps/frontend/src/features/studio/api/{end_conditions,invariants,playtest,duplicate}.api.ts`
- `apps/frontend/src/features/studio/hooks/{useEndConditions,useInvariants,usePlaytest,useDuplicateScenario}.ts`
- `apps/frontend/src/features/studio/types/{end_condition,invariant}.types.ts`

**Files to modify:**
- `apps/frontend/src/features/studio/stores/studio.store.ts` — add master-mode UI state (`activeTab`, not persisted server-side).
- `apps/frontend/src/features/studio/pages/EditScenarioPage.tsx` — branch on `scenario.mode` to render `StudioDocumentLayout` (newbie, existing) or `MasterModeStudioLayout` (new).
- **Backend (small, thin endpoints not warranting their own spec):**
  - `apps/core-api/app/routers/scenarios.py` + `app/services/scenario_service.py` — add `POST /v1/scenarios/{id}/playtest` (creates a `Playthrough` with `is_playtest=true`, reusing `PlaythroughService.create_playthrough` with a flag — no new pipeline logic, `master-mode-end-conditions.spec.md`'s `is_playtest` column already exists for this) and `POST /v1/scenarios/{id}/duplicate` (deep-copies a scenario's rows: `Scenario` + `entities` + `facts` + `scenario_conditions` + `end_conditions` + `rule_invariants`, new `scenario_id`s throughout, status forced to `draft`).

### 3.4. Code Style & Interfaces

#### `MasterModeStudioLayout.tsx` — tabs shell (dense, per the locked decision, not a wizard):

```tsx
import { useState } from "react";
import { AIChatSidebar } from "../AIChatSidebar/AIChatSidebar";
import { EntityEditor } from "../EntityEditor/EntityEditor";
import { FactEditor } from "../FactEditor/FactEditor";
import { ConditionEditor } from "../ConditionEditor/ConditionEditor";
import { StateSchemaEditor } from "../StateSchemaEditor/StateSchemaEditor";
import { EndConditionsEditor } from "../EndConditionsEditor/EndConditionsEditor";
import { InvariantEditor } from "../InvariantEditor/InvariantEditor";

const TABS = [
  { id: "entities", label: "Entities" },
  { id: "facts", label: "Facts" },
  { id: "state", label: "State Schema" },
  { id: "conditions", label: "Active Conditions" },
  { id: "invariants", label: "World Rules" },
  { id: "endings", label: "Endings" },
  { id: "setup", label: "Setup & Narrator" },
] as const;

type TabId = (typeof TABS)[number]["id"];

interface MasterModeStudioLayoutProps {
  scenarioId: string;
}

export const MasterModeStudioLayout: React.FC<MasterModeStudioLayoutProps> = ({
  scenarioId,
}) => {
  const [activeTab, setActiveTab] = useState<TabId>("entities");
  // Panel content is switched, not scrolled to — dense/structured, not a
  // single long document (locked decision, contrast with StudioDocumentLayout).
  return (
    <div className="flex flex-1 overflow-hidden bg-zinc-950 font-sans text-zinc-300">
      <nav className="w-56 border-r border-zinc-800 flex-shrink-0 p-4 space-y-1">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`w-full text-left px-3 py-2 text-sm ${
              activeTab === tab.id
                ? "bg-zinc-900 text-zinc-100 font-medium"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </nav>
      <main className="flex-1 overflow-y-auto p-8">
        {activeTab === "entities" && <EntityEditor scenarioId={scenarioId} />}
        {activeTab === "facts" && <FactEditor scenarioId={scenarioId} />}
        {activeTab === "state" && <StateSchemaEditor scenarioId={scenarioId} />}
        {activeTab === "conditions" && <ConditionEditor scenarioId={scenarioId} />}
        {activeTab === "invariants" && <InvariantEditor scenarioId={scenarioId} />}
        {activeTab === "endings" && <EndConditionsEditor scenarioId={scenarioId} />}
        {/* "setup" tab composes SetupSchemaEditor, OpeningSceneEditor,
            NarratorPersonaEditor, NarrationFontPicker, ActionChipsEditor,
            RulesEditor — omitted here for brevity, same composition pattern. */}
      </main>
      {/* Right-pane AI chat drawer — reused verbatim from StudioDocumentLayout,
          extract the drawer chrome into a shared StudioChatDrawer.tsx during
          implementation rather than duplicating the toggle/animation JSX. */}
    </div>
  );
};
```

#### `ExpressionBuilder` — the single shared implementation (types, `.tsx` body implements the picker composition):

```typescript
// ConditionEditor/ExpressionBuilder/ExpressionBuilder.types.ts
export type ExpressionOperator =
  | "==" | "!=" | "<" | "<=" | ">" | ">=" | "in" | "contains" | "matches";

export interface FieldExpression {
  field: string;       // dot-path: "player.health" or "the_warden.awareness"
  op: ExpressionOperator;
  value: string | number | boolean;
  AND?: FieldExpression;
  OR?: FieldExpression;
  NOT?: FieldExpression;
}

export interface AvailableField {
  path: string;        // "player.health"
  label: string;        // creator-facing label, from state_schema's `label`
  type: "string" | "number" | "boolean" | "enum" | "entity_ref";
}
```

```tsx
// ExpressionBuilder.tsx — consumes availableFields (built by the caller from
// useScenario().state_schema + useEntities() attributes_schema, see below),
// never fetches its own data — a pure, reusable expression-tree editor.
interface ExpressionBuilderProps {
  value: FieldExpression | null;
  onChange: (expr: FieldExpression | null) => void;
  availableFields: AvailableField[];
}
```

The `availableFields` list is assembled once per screen by whichever parent uses `ExpressionBuilder` (`ConditionEditor`, `EndConditionsEditor`, `InvariantEditor`) via a small shared helper `buildAvailableFields(stateSchema, entities)` — one function, colocated in `ExpressionBuilder/availableFields.ts`, so `FieldPicker`'s "does this path actually exist" real-time check has one source of truth across all three consumers.

#### `StateSchemaEditor` field shape (drives both the JSON built for the backend and the terminology-relabel UI via `label`):

```typescript
export type StateFieldType =
  | "string" | "number" | "boolean" | "enum"
  | "entity_ref" | "list" | "object" | "derived";

export interface StateFieldDefinition {
  type: StateFieldType;
  label?: string;              // relabeling: shown to the player instead of the key
  initial?: unknown;
  min?: number;
  max?: number;
  entity_type?: string;        // for entity_ref/list-of-entity_ref
  fields?: Record<string, StateFieldDefinition>;  // for object
  item_type?: StateFieldType;                      // for list
  formula?: string;             // for derived, read-only display
}
```

#### Setup archetypes (extends `SetupSchemaEditor.tsx`), matching the demo scenario's Warrior/Scholar example:

```typescript
export interface SetupArchetype {
  id: string;
  name: string;               // "Warrior"
  values: Record<string, unknown>;  // { "player.health": 100, "player.inventory": ["rustbound_blade"] }
}
```

Rendered on the Play surface's setup screen as selectable presets (out of this spec's scope to implement the Play-surface consumption — that's a Play-feature concern; this spec only authors and persists `Scenario.setup_archetypes`, flagged as a cross-feature dependency in §4).

### 3.5. Git & Review Workflow

- Branch: `feat/master-mode-studio-ui`
- Depends on `master-mode-data-model.spec.md` (all CRUD endpoints), `master-mode-end-conditions.spec.md` (`priority`/`is_playtest` columns), and ideally `master-mode-turn-pipeline.spec.md`/`master-mode-memory-contract.spec.md` merged first, though this spec's frontend work can proceed against a mocked API if backend sequencing slips.
- Commit scope: one commit per major component group (entities, facts, expression-builder-family, state-schema, conditions+invariants, end-conditions, the new small-feature components, the two thin backend endpoints).
- PR checklist: `tsc --noEmit` clean; no feature-to-feature imports (studio never imports from `play/`); every new hook is React-Query-backed, no `useEffect`+`useState` data fetching.

### 3.6. Boundaries (Three-Tier Model)

- ✅ **Always:** build `ExpressionBuilder`'s `availableFields` from live `state_schema`/entity data, never a hardcoded list; run real-time reference validation against already-loaded query-cache data before hitting the network; keep `AIChatSidebar` advisory-only (it must never call any entity/fact/condition mutation hook itself).
- ⚠️ **Ask First:** any change to the tab set in `MasterModeStudioLayout` beyond what's listed here; making `EntityEditor`'s attribute schema editor a fully separate component tree instead of the smaller `StateSchemaEditor` sibling described above (keeping them close in shape matters for consistency).
- 🚫 **Never:** let `studio/` import anything from `play/` (feature boundary, CLAUDE.md); duplicate `ExpressionBuilder` logic inside `EndConditionsEditor` or `InvariantEditor` instead of importing the shared component; use inline styles instead of Tailwind utility classes.

## 4. Edge Cases, Rate Limits & Graceful Degradation

- **Large entity/fact counts in `FieldPicker`/entity pickers:** no pagination added in this spec (matches the "real scale, not simulated scale" posture of `master-mode-memory-contract.spec.md`) — if this becomes a real UX problem at demo scale, a searchable combobox (already-available shadcn `Select` pattern) is the fix, not pagination; flagged here rather than silently deferred.
- **Concurrent edits (two tabs editing the same scenario):** out of scope — matches the existing newbie-mode authoring surface's posture (no optimistic-locking/conflict UI exists there either); not a regression this spec introduces.
- **Setup-archetype / opening-scene / font / action-chips consumption on the Play surface:** this spec only authors and persists these fields on `Scenario`. Actually rendering them on the Play surface (setup screen archetype picker, opening-scene display, font application, action chips as quick-input buttons) is `play/` feature work, explicitly out of this spec's scope (studio and play never cross-import) — flagged as a **required follow-up spec** before these features are player-visible, not assumed to fall out "for free."
- **Playtest mode and discovery/rating pollution:** a playtest playthrough must never appear in `list_public_playthroughs`, never count toward `play_count`, and — since ratings require `turn_count >= 10` on *any* playthrough per the existing rating rule — must also be excluded from the rating-eligibility check, or a creator could farm their own review eligibility via playtesting. `apps/core-api/app/services/scenario_service.py`'s `has_user_played_min_turns` needs a `WHERE NOT is_playtest` filter — noted here since it's a one-line but easy-to-miss change alongside this spec's playtest endpoint.

## 5. Phased Implementation Tasks (Task Checklist)

- [ ] **Task 1 (API/hooks/types foundation):** Fill `api/{entities,facts,conditions}.api.ts`, create `api/{end_conditions,invariants}.api.ts`, and their matching `hooks/`/`types/` files. Verify: `tsc --noEmit`.
- [ ] **Task 2 (ExpressionBuilder family):** Implement `FieldPicker`, `OperatorPicker`, `ValueInput`, `ExpressionBuilder`, and `availableFields.ts`. Verify: `npx vitest run src/features/studio/components/ConditionEditor/ExpressionBuilder`.
- [ ] **Task 3 (Entities & Facts):** Implement `EntityEditor` (+ `AttributesSchemaEditor`) and `FactEditor`, with real-time reference validation. Verify: `npx vitest run src/features/studio/components/EntityEditor src/features/studio/components/FactEditor`.
- [ ] **Task 4 (State schema, conditions, invariants, endings):** Implement `StateSchemaEditor`, `ConditionEditor` (+ Effect C mutation sub-form), `InvariantEditor`, `EndConditionsEditor` (+ priority reorder). Verify: `npx vitest run` on each.
- [ ] **Task 5 (Layout + small features):** Implement `MasterModeStudioLayout`, wire into `EditScenarioPage.tsx`; implement `OpeningSceneEditor`, `NarrationFontPicker`, `ActionChipsEditor`, `RulesEditor`, extend `SetupSchemaEditor` for archetypes and `NarratorPersonaEditor` for checkpoint overrides. Verify: manual dev-server walkthrough of "The Hollow Cairn" end-to-end authoring.
- [ ] **Task 6 (Playtest + duplicate):** Add the two thin Core API endpoints; implement `PlaytestButton`/`DuplicateScenarioButton` + their hooks; add the `has_user_played_min_turns` playtest-exclusion filter. Verify: `pytest` (backend) + `npx vitest run` (frontend) for both.
