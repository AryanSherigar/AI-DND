# Frontend Architecture — Shared Layer & Infrastructure

This document details the shared UI primitives, hooks, core clients, utilities, and audio engine located in `apps/frontend/src/shared/`.

---

## 1. Overview & Shared Rules

In accordance with [CLAUDE.md](file:///home/aryan-sherigar/projects/AI-DND/CLAUDE.md):
- **`shared/` contains no feature-specific logic**: Code in `shared/` must be agnostic to whether it is rendered in Studio, Play, or Profile.
- **Single Source of Truth for Network I/O**:
  - `shared/lib/api-client.ts`: Sole executor of standard HTTP requests.
  - `shared/lib/sse-client.ts` & `shared/hooks/useSSE.ts`: Sole handlers of Server-Sent Event streaming.
- **One Component per File**: Every component file exports exactly one component.

---

## 2. Core Libraries (`src/shared/lib/`)

### `apps/frontend/src/shared/lib/sse-client.ts` & `useSSE.ts`
- **Purpose & Layer:** Centralized Server-Sent Event stream managers.
- **Key Functions & Types:**
  - `createGetSSEConnection(url, token, handlers)`: Uses native `EventSource` or `fetch` with ReadableStream to establish persistent SSE connections. Passes auth tokens via URL or headers.
  - `createPostSSEConnection(url, body, token, handlers)`: Dispatches `POST` requests and streams response chunks line-by-line, parsing `event:` and `data:` markers.
  - `useSSE(url, onEvent, enabled)`: React lifecycle wrapper hook. Automatically connects on mount and cleans up on unmount.
- **Architecture Invariant:** Components are strictly forbidden from instantiating `EventSource` directly; all streaming flows through `useSSE`.

### `apps/frontend/src/shared/lib/api-client.ts`
- **Purpose & Layer:** Core HTTP client wrapper around `fetch`.
- **Key Features:**
  - Injects `Authorization: Bearer <token>` from `auth.store.ts`.
  - Injects `X-Request-Id` using `request-id.ts` for distributed tracing.
  - Auto-unwraps JSON and maps HTTP 4xx/5xx errors into typed client error objects.

### `apps/frontend/src/shared/lib/query-client.ts`
- **Purpose & Layer:** Global TanStack React Query configuration (`QueryClient`).
- **Key Settings:**
  - Configures default stale times: `staleTime: 1000 * 60 * 5` (5 minutes) for static discovery feeds; playthrough active states configure `staleTime: 0` for fresh consistency.

### `apps/frontend/src/shared/lib/firebase.ts`
- **Purpose & Layer:** Google Firebase client SDK initializer (`initializeApp`, `getAuth`, `GoogleAuthProvider`).

### `apps/frontend/src/shared/lib/logger.ts`
- **Purpose & Layer:** Client-side telemetry logger formatting JSON logs and forwarding fatal frontend exceptions to `/v1/logs`.

### `apps/frontend/src/shared/lib/audio/ambient-soundtrack.ts`
- **Purpose & Layer:** Web Audio API adaptive background music synthesis engine.
- **Key Exports & Architecture:**
  - `AmbientSoundtrackController`: Dual-channel (`channelA`, `channelB`) crossfading audio player.
  - `CROSSFADE_DURATION_SECONDS = 4.0`: Smooth 4-second crossfade curve between mood tracks.
  - `MIN_COOLDOWN_MS = 45000`: 45-second stabilization cooldown preventing jarring musical shifts when narration moods fluctuate rapidly.
  - Connects to generated mood WAV tracks in `/audio/moods/` (`peaceful.wav`, `mystery.wav`, `tension.wav`, `combat.wav`, `melancholy.wav`).
  - Manages Web Audio `AudioContext` unlocking upon initial user interaction.

---

## 3. UI Primitives & Design System (`src/shared/components/`)

### Layout Components (`components/layout/`)
- **`AppShell.tsx`**: Universal root frame with sticky top navigation header, responsive padding, and dark-fantasy parchment background.
- **`Header.tsx`**: Main navigation bar with logo, surface switch links (`Discover`, `Studio`), and user auth menu.

### UI Form & Surface Components (`components/ui/`)
- **`Button.tsx`**: Stylized button supporting `primary`, `secondary`, `outline`, `ghost`, and `danger` variants, plus loading spinners.
- **`Input.tsx` & `Select.tsx`**: Themed form inputs with label and error state styling.
- **`Card.tsx`**: Container card with border motifs and subtle background blurs.
- **`Modal.tsx`**: Accessible modal overlay with backdrop click-outside dismissal and Esc key handling.
- **`Badge.tsx`**: Metadata chips for genres, tags, and status indicators.
- **`Separator.tsx`**: Decorative ornamental horizontal dividers.
- **`ExpandablePanel.tsx`**: Collapsible accordion panels with animated chevron toggles.
- **`EmptyState.tsx`**: Fallback view displaying an empty-state illustration and action button.

### Feedback & Icons
- **`Toast.tsx`**: Ephemeral floating notification toasts.
- **`LoadingSpinner.tsx`**: Stylized spinning indicator.
- **`ErrorBoundary.tsx`**: React class component catching render errors and displaying recovery options.
- **`CleanIcons.tsx` & `PixelIcons.tsx`**: SVG icon sets for UI actions and retro pixel art motifs.

---

## 4. Shared Constants & Types (`src/shared/constants/` & `types/`)

- **`genres.ts`**: Canonical scenario genres (`High Fantasy`, `Cyberpunk`, `Cosmic Horror`, `Steampunk`, `Post-Apocalyptic`, etc.) and accent colors.
- **`content-tags.ts`**: Audience age ratings: `all-ages`, `teen`, `mature`.
- **`complexity-tiers.ts`**: Mode metadata: `Newbie` vs `Master`.
- **`predicates.ts`**: Standard triplet fact verbs (`located_in`, `allied_with`, `possesses`, `opposes`).
- **`narration-fonts.ts`**: Typography styles selectable by scenario authors (`Cinematic Serif`, `Modern Sans`, `Retro Pixel`, `Gothic Manuscript`).
- **`api.types.ts` & `common.types.ts`**: TypeScript interfaces mirroring Core API and TRS HTTP schemas.
