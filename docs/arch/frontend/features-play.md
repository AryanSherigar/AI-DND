# Frontend Architecture — Play Surface

This document details the components, hooks, stores, and API clients in `apps/frontend/src/features/play/`, which powers the player-facing experience across discovery, scenario setup, live gameplay, and spectator broadcasting.

---

## 1. Overview & Gameplay Lifecycle

The Play surface guides the user through four sequential phases:
1. **Discovery & Exploration (`/discover`, `/scenario/:id`)**: Browsing scenarios, viewing reviews, and reading lore summaries.
2. **Character Setup (`/setup/:id`)**: Selecting archetypes, adjusting attribute points, and naming characters.
3. **Turn Resolution & Living Book (`/play/:id`)**: Immersive dual-pane book canvas, live SSE narration streaming, dynamic audio soundtrack, and entity tooltip codex.
4. **Social Sharing & Spectating (`/spectate/:id`, `/join`)**: Spectator streaming and multiplayer turn coordination.

```mermaid
flowchart LR
    Discovery["DiscoveryFeed / ScenarioFocus"] -->|Selects Scenario| Setup["SetupScreen<br/>(Archetype & Stats)"]
    Setup -->|POST /playthroughs| PlayScreen["PlayScreen / EBookCanvas<br/>(Living Book Interface)"]
    PlayScreen -->|POST /turn (useTurnStream)| TRS["Turn Resolution Service"]
    TRS -->|SSE Chunks & [DONE]| PlayScreen
    PlayScreen -.->|Broadcasts via Share Token| Spectator["SpectatorView (/spectate/:id)"]
```

---

## 2. Component Subsystems

### A. E-Book Living Reader Canvas (`src/features/play/components/PlayScreen/EBook/`)
The E-Book UI represents a skeuomorphic parchment reading interface with dynamic ambient lighting and interactive entity inspection:
- **`EBookCanvas.tsx`**: Dual-page or scrollable book parchment container. Manages turn entries, book margins, ambient audio volume, and drawer toggles.
- **`EBookTurnEntry.tsx`**: Renders individual turns with decorative drop-caps, action headers, and streaming narration markdown.
- **`EBookActionDrawer.tsx`**: Slide-up drawer containing the player action input, mode pills (Speak, Act, Custom), and turn submission controls.
- **`EBookCodexDrawer.tsx`**: Slide-out world encyclopedia displaying known entities, discovered lore facts, and current character attributes.
- **`useEntityHighlighter.ts` & `EntityInspectTooltip.tsx`**: Custom regex parser scanning narration text for registered scenario entities and keywords; renders interactive hovering tooltips with entity portraits and lore snippets.
- **`EBookAudioControl.tsx`**: Minimal volume and mood soundtrack widget.
- **`ChronicleRecapModal.tsx`**: High-level narrative synopsis modal summarizing past turns.

### B. Discovery Feed (`src/features/play/components/DiscoveryFeed/`)
- **`DiscoveryFeed.tsx`**: Virtualized scenario grid with infinite scroll.
- **`ScenarioCard.tsx` & `WideScenarioCard.tsx`**: Rich scenario cards displaying cover art, genre badges, author avatar, play count, and star rating.
- **`FeedFilters.tsx` & `AdvancedFiltersModal.tsx`**: Multi-select filtering by genre, complexity tier (Newbie vs. Master), and player count support (Solo, Duo, Party).
- **`FeedSortBar.tsx`**: Sort toggles (`trending`, `recent`, `rating`).
- **`TopSearchBar.tsx`**: Debounced full-text search input.

### C. Scenario Focus (`src/features/play/components/ScenarioFocus/`)
- **`ScenarioFocusPage.tsx`**: Detailed landing hero for a single scenario.
- **`ScenarioBannerHero.tsx`**: Cinematic cover art banner and play CTA.
- **`ScenarioLoreSection.tsx`**: Lore preview and world hook.
- **`ScenarioReviewsSection.tsx`**: Player rating distributions and reviews list.
- **`ScenarioPublicPlaythroughs.tsx`**: Live spectator links for active community sessions.

### D. Setup & Character Creation (`src/features/play/components/SetupScreen/`)
- **`SetupScreen.tsx`**: Multi-stage character creation wizard.
- **`SetupStageCard.tsx`**: Card for picking character archetype presets.
- **`SetupField.tsx`**: Input row for configuring custom stat values or narrative backstories.
- **`DramaticSetupLoader.tsx`**: Atmospheric transition loader while the playthrough instance is initialized and memory cloned.

### E. Cartography & Spectator
- **`MapViewer.tsx`**: Interactive pan-and-zoom map viewer displaying discovered pins, connections, and player position markers.
- **`SpectatorView.tsx`**: Read-only real-time narration stream consuming the spectator SSE channel.

---

## 3. Hooks & API Layer

### Hooks (`src/features/play/hooks/`)
- **`useTurnStream.ts`**: Core hook managing the turn submission lifecycle. Connects to `POST /v1/turn` via `useSSE`, buffers incoming token chunks, extracts dynamic `[mood: ...]` soundtrack tags to feed the audio engine, and triggers React Query cache invalidation upon stream completion.
- **`usePlaythrough.ts`**: React Query hook fetching playthrough state and participant sheets (`GET /v1/playthroughs/:id`).
- **`useDiscovery.ts`**: React Query hook managing paginated scenario discovery feed queries.
- **`useScenarioFocus.ts`**: Fetches scenario details, reviews, and public sessions.
- **`useSpectator.ts`**: Manages spectator SSE stream subscription (`/v1/session/:id/spectate`).
- **`useNotifications.ts`**: Subscribes to `"your_turn"` SSE notifications in multiplayer playthroughs.
- **`useUpdateCharacterFields.ts`**: Mutation hook for client-side state patches.

### API Clients (`src/features/play/api/`)
- **`turns.api.ts`**: Executes turn submissions.
- **`playthroughs.api.ts`**: Creates playthroughs, enrolls participants, and abandons sessions.
- **`discovery.api.ts`**: Queries public scenario catalog.
- **`scenarioFocus.api.ts`**: Fetches scenario metadata and public sessions.
- **`ratings.api.ts`**: Submits reviews and fetches scenario ratings.
- **`share.api.ts`**: Resolves share tokens for spectator links.

---

## 4. State Management (`src/features/play/stores/play.store.ts`)

- **Purpose & Layer:** Zustand client UI store for the Play surface.
- **State Tracked:**
  - `isActionDrawerOpen: bool`: Visibility of the player input drawer.
  - `isCodexDrawerOpen: bool`: Visibility of the entity encyclopedia.
  - `activeActionMode: "speak" | "act" | "custom"`: Player action prefix mode.
  - `selectedEntityForInspection: Entity | None`: Currently inspected entity in the codex.
  - `isAudioMuted: bool`, `audioVolume: number`: Soundtrack player controls.
- **Architecture Rules & Invariants:** Does not store playthrough or scenario entity models; all server state remains exclusively inside TanStack React Query.
