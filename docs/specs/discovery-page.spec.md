# Spec: Discovery Page (YouTube-Style Search Feed)

## 1. Objective & User Outcome
- **Problem Statement:** Players need a robust, dedicated interface to browse, filter, and search through all published scenarios. The current Landing Page focuses on curation and hero aesthetics, lacking the dense information and advanced filtering needed for deep discovery.
- **User Story:** As a player, I want to use a YouTube-style search feed with a sidebar, quick filter pills, and an advanced centered-modal for filters so that I can easily find the exact type of scenario I want to play based on complexity, genre, and social signals.
- **Success Criteria:** 
  - Implementation of a responsive left sidebar navigation.
  - A top search bar with horizontally scrollable quick filter pills.
  - Single-column list layout where each result is a wide landscape card (16:9 thumbnail) displaying rich metadata and the creator's description.
  - Clicking "Play" starts the setup; clicking the card opens the Scenario Information Page.

## 2. Technical Architecture & Data Flow
- **Components Involved:** 
  - `DiscoveryPage.tsx` (Layout container with Sidebar and Main Content)
  - `DiscoverySidebar.tsx` (Left navigation: Home, Profile, Create, You sections, Genres)
  - `TopSearchBar.tsx` (Search input and quick filter pills)
  - `DiscoveryFeed.tsx` (Infinite scroll or paginated container)
  - `WideScenarioCard.tsx` (16:9 image, title, creator, playtime, plays, ratings, description, Play button)
  - `AdvancedFiltersModal.tsx` (Centered modal for exhaustive filtering)
- **Sequence Flow:** 
  1. User navigates to `/discover`.
  2. `useDiscovery` hook fetches scenarios from Core API via `GET /v1/scenarios` (with URL query parameters).
  3. URL query parameters (`?q=...&mode=...&genre=...`) act as the single source of truth for the active filter state.
  4. User clicks a quick pill (e.g., "Master"); URL updates to `?mode=master`, triggering a re-fetch.
  5. Search results render as `WideScenarioCard`s.

## 3. The Six Core Engineering Dimensions
### 3.1. Commands
- Build: `npm run build` (within `apps/frontend`)
- Test: `npm run test` (within `apps/frontend`)
- Lint / Type-Check: `npm run lint && npm run typecheck`

### 3.2. Testing Strategy & Conformance
- Ensure `useDiscovery` correctly parses URL parameters and passes them to the API fetcher.
- Visual conformance: Cards must enforce 16:9 aspect ratios for images and truncate descriptions that are too long.

### 3.3. Project Structure & File Layout
- Files to create: 
  - `apps/frontend/src/features/play/components/DiscoverySidebar.tsx`
  - `apps/frontend/src/features/play/components/TopSearchBar.tsx`
  - `apps/frontend/src/features/play/components/WideScenarioCard.tsx`
  - `apps/frontend/src/features/play/components/AdvancedFiltersModal.tsx`
- Files to modify: 
  - `apps/frontend/src/app/router.tsx` (add route for `/discover`)
  - `apps/frontend/src/features/play/pages/DiscoveryPage.tsx`
  - `apps/frontend/src/features/play/hooks/useDiscovery.ts`

### 3.4. Code Style & Interfaces
```typescript
interface DiscoveryFilters {
  query?: string;
  mode?: "newbie" | "master" | "all";
  playerCount?: "solo" | "multiplayer" | "all";
  sort?: "popular" | "trending" | "newest";
  genres?: string[];
  minPlays?: number;
}
```

### 3.5. Git & Review Workflow
- Suggested branch name: `feat/discovery-page-redesign`
- PR must include visual validation (screenshots) confirming layout matches the YouTube-style wireframe and adheres to AI-DND's typography/color palette.

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** Maintain strict separation between `shared/` components and `play/` feature components. Use Tailwind utilities.
- ⚠️ **Ask First:** Modifying the Core API `GET /v1/scenarios` if it doesn't currently support these search parameters.
- 🚫 **Never:** Disable strict TypeScript checks for complex filter states.

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Empty States:** Render a stylized "No Adventures Found" empty state if filter combination is too restrictive, with a "Clear Filters" button.
- **Loading:** Use skeleton loaders shaped like the `WideScenarioCard` (16:9 box + text lines) while fetching.
- **Responsive:** Sidebar becomes a bottom nav or hamburger menu on mobile screens to preserve horizontal space.

## 5. Phased Implementation Tasks (Task Checklist)
- [ ] **Task 1 (Routing & Layout Shell):** Define `/discover` route, build the overall layout grid (Sidebar + Main Content Area).
- [ ] **Task 2 (Sidebar Component):** Implement `DiscoverySidebar.tsx` with Home, Profile, Create, You (Previous, Saved, Liked, Created), and Genres sections.
- [ ] **Task 3 (Top Bar & Pills):** Implement `TopSearchBar.tsx` with text input and quick pills (All, Newbie, Master, Solo, Multiplayer, Popular, Trending). Sync with URL search params.
- [ ] **Task 4 (Wide Scenario Card):** Build `WideScenarioCard.tsx` incorporating 16:9 image, description snippet, play button, and metadata.
- [ ] **Task 5 (Advanced Modal & Hook integration):** Build `AdvancedFiltersModal.tsx` and connect `useDiscovery` to fetch data based on the full filter state.
