# Spec: Live Play Screen — Real Turn Streaming, History, Spectate, Share/Join

## 1. Objective & User Outcome
- **Problem Statement:** The Play surface is a fully mocked UI shell today. `usePlayStore.submitTurn` calls `simulateTokenStream(...)` from `mock/playthroughMock.ts` — a local fake token generator — instead of calling TRS; `PlayPage.tsx` always seeds `turns: []` and never fetches history; `shared/hooks/useSSE.ts` and `shared/lib/sse-client.ts` (the CLAUDE.md-mandated single point for `EventSource` usage) are both 0-byte files, so no SSE plumbing exists anywhere in the frontend; `hooks/useTurnStream.ts`, `useNotifications.ts`, `useSpectator.ts`, `api/share.api.ts`, `api/turns.api.ts` are all 0-byte files; `SpectatorView.tsx` is a 0-byte file with no route; `SharePlaythroughModal.tsx` builds share URLs by client-side string interpolation with no backend call. This spec makes the Play surface real, consuming the backend built in `trs-turn-endpoint-and-memory-wiring.spec.md` and `sharing-and-multiplayer.spec.md`.
- **User Story:** As a player, I want my submitted action to actually reach the AI narrator and stream back real narration that persists, want to scroll back through my playthrough's real history, want a working share link, and — as a spectator or a joined multiplayer participant — want to see live narration and know when it's my turn.
- **Success Criteria:**
  - Submitting an action in `ActionInput` calls real `POST /v1/turn` via SSE and renders genuine Gemini narration token-by-token; `mock/playthroughMock.ts`'s `simulateTokenStream` is no longer called from `play.store.ts`.
  - `PlayPage` loads real turn history via `GET /v1/playthroughs/{id}/turns` on mount.
  - `SharePlaythroughModal` calls the real `POST /v1/playthroughs/{id}/share` endpoint and displays the real token-bearing URL.
  - A `/spectate/:id` (or equivalent) route renders live narration via `GET /v1/session/{id}/spectate`, read-only.
  - A join flow exists: opening a `join`-mode share URL lets an authenticated user call `POST /v1/playthroughs/join` and land in `PlayPage` as a real participant.
  - Multiplayer participants see their action input enabled/disabled based on `your_turn` notifications from `GET /v1/session/{id}/notifications`.
  - `raw EventSource` never appears outside `shared/lib/sse-client.ts` (CLAUDE.md hard rule).

## 2. Technical Architecture & Data Flow
- **Components Involved:**
  - **`shared/lib/sse-client.ts` (filled in):** the only file that instantiates `EventSource`. Exposes a small factory: `createSSEConnection(url: string, handlers: {onEvent(name, data), onError, onOpen}): () => void` (returns a disposer). Handles named SSE events (`narration`, `done`, `degraded`, `your_turn`, etc.) via `addEventListener` per event name, since the backend uses named events, not the default `message` event.
  - **`shared/hooks/useSSE.ts` (filled in):** thin React wrapper around `sse-client.ts` — `useSSE(url, handlers, enabled)` — manages connect/disconnect on mount/unmount/dependency change, exposes connection status. This is the file CLAUDE.md requires every feature-level SSE hook to route through.
  - **`features/play/hooks/useTurnStream.ts` (filled in):** wraps `useSSE` for `POST /v1/turn`. Because the RFC's turn endpoint is a POST-then-stream (not a `GET` `EventSource`-compatible URL), this hook cannot use the browser's native `EventSource` (which only supports GET) — it must use `fetch` with a `ReadableStream` reader and manually parse SSE framing (`event:`/`data:` lines), OR `sse-client.ts` gains a second factory `createPostSSEConnection(url, body, handlers)` built on `fetch`. **Decision for this spec: extend `sse-client.ts` with `createPostSSEConnection`, keeping it the sole SSE entrypoint** (still satisfies the CLAUDE.md boundary — the constraint is "no raw `EventSource`/stream handling outside this file," not "only `EventSource`").
  - **`features/play/hooks/useNotifications.ts` (filled in):** wraps `useSSE` for `GET /v1/session/{id}/notifications` (a real `EventSource`-compatible GET endpoint, persistent connection). Lives for the lifetime of `PlayPage`.
  - **`features/play/hooks/useSpectator.ts` (filled in):** wraps `useSSE` for `GET /v1/session/{id}/spectate?share_token=...` (GET, `EventSource`-compatible).
  - **`features/play/api/turns.api.ts` (filled in):** `getTurns(playthroughId, params)` → `GET /v1/playthroughs/{id}/turns`.
  - **`features/play/api/share.api.ts` (filled in):** `createShare(playthroughId, mode)` → `POST /v1/playthroughs/{id}/share`; `joinPlaythrough(shareToken)` → `POST /v1/playthroughs/join`.
  - **`features/play/stores/play.store.ts` (modified):** `submitTurn` no longer calls `simulateTokenStream`; instead it triggers `useTurnStream`'s imperative `start(actionText)` (the mutation lives in the hook, not the store, per CLAUDE.md's React Query rule — "no `useEffect` + `useState` pattern for data fetching," and SSE-driven mutations belong in a hook, not duplicated store logic). The store keeps only client-only UI state (`streaming_text`, `is_narrating`, sidebar state) — genuinely server-derived data (turn history) moves to React Query via `useTurns`, not the store.
  - **`features/play/hooks/useTurns.ts` (new, thin React Query wrapper around `turns.api.ts`):** `usePlaythroughTurns(playthroughId)`.
  - **`features/play/pages/PlayPage.tsx` (modified):** on mount, loads `usePlaythroughTurns(id)` and seeds `play.store`'s turn history instead of the hardcoded `turns: []`; mounts `useNotifications(id, participantId)` for multiplayer.
  - **`features/play/pages/SpectatorPage.tsx` (new) + `components/SpectatorView/SpectatorView.tsx` (filled in):** new route `/spectate/:id?token=...`; loads history via `usePlaythroughTurns`, then subscribes via `useSpectator`.
  - **`features/play/pages/JoinPage.tsx` (new):** new route `/join?token=...`; on mount (auth-gated), calls `joinPlaythrough(token)`, then navigates to `/play/:playthrough_id`.
  - **`app/router.tsx` (modified):** register `/spectate/:id` and `/join` routes.
  - **`components/PlayScreen/SharePlaythroughModal.tsx` (modified):** calls `share.api.ts`'s `createShare` for both modes instead of client-side string interpolation.
  - **`mock/playthroughMock.ts`:** `simulateTokenStream` and `INITIAL_MOCK_PLAYTHROUGH` are deleted or reduced to Storybook/dev-only fixtures explicitly not imported by `play.store.ts` anymore — CLAUDE.md's "no half-finished implementations" cuts both ways: don't leave dead mock code wired into the real store.

- **Sequence Flow — Real turn submission:**
  1. Player types an action, `ActionInput.handleSubmit` calls `usePlayStore.submitTurn(actionText)`.
  2. `submitTurn` sets `is_narrating: true`, calls `useTurnStream`'s `start(actionText)` (exposed via the store holding a reference set by `PlayScreen`/`ActionInput` mounting the hook — or, cleaner: `ActionInput` calls `useTurnStream().start(text)` directly and only pushes UI-state updates to the store via the hook's callbacks. **This spec commits to the cleaner version**: `useTurnStream` is called from `ActionInput` (or a new `PlayScreen`-level wrapper), not indirectly through the store.
  3. `useTurnStream.start` opens a `createPostSSEConnection` to `POST /v1/turn` with `{playthrough_id, participant_id, action_text}`.
  4. `narration` events append to `play.store.streaming_text` via the hook's `onEvent` callback (still updates the store — that's legitimate client-side streaming UI state, not server state).
  5. `done` event: hook calls `usePlaythroughTurns`'s query invalidation (`queryClient.invalidateQueries(["playthrough-turns", id])`) so the new turn appears in the authoritative history next render, clears `streaming_text`, sets `is_narrating: false`.
  6. `degraded` event: shows an error toast (`shared/components/feedback/Toast.tsx`, already exists) with the degradation message from the backend; does not clear the player's typed action (nothing to clear — action already submitted; instead, surface a "your turn may not have saved, you can try again" message per the RFC's stated degradation UX).

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- **Type-check:** `cd apps/frontend && npx tsc --noEmit`
- **Lint/Format:** `cd apps/frontend && npx prettier --write . && npx eslint . --fix`
- **Build:** `cd apps/frontend && npm run build`
- **Manual verification:** `npm run dev`, log in, create a newbie scenario, publish, start a playthrough, submit an action, confirm real streamed narration appears (network tab shows `POST /v1/turn` with a `text/event-stream` response), reload the page and confirm the turn persisted via `GET /v1/playthroughs/{id}/turns`.

### 3.2. Testing Strategy & Conformance
- **Framework:** React Testing Library + `msw` (CLAUDE.md: mock API calls at the network level, not React Query internals). SSE responses can be tested by having `msw` intercept the `fetch`-based POST-SSE call and return a canned `ReadableStream` body with SSE-framed chunks.
- **No snapshot tests** for `PlayScreen`/`ActionInput`/`SpectatorView` (logic components, not presentational leaves) — test user behavior.
- **Deterministic test cases:**
  1. `sse-client.ts`: `createPostSSEConnection` correctly parses multi-event SSE framing (`event: narration\ndata: ...\n\n` followed by `event: done\ndata: \n\n`) into separate `onEvent` calls.
  2. `useTurnStream`: submitting an action triggers the POST with the correct body; `narration` events accumulate; `done` triggers the expected callback (history invalidation).
  3. `ActionInput`: typing and submitting disables the input while `is_narrating`, re-enables after `done`.
  4. `PlayPage`: on mount with a valid `id`, renders fetched turn history (via `msw`-mocked `GET /v1/playthroughs/{id}/turns`), not an empty list.
  5. `SharePlaythroughModal`: clicking "Generate spectate link" calls the real endpoint (via `msw`) and renders the returned token-bearing URL, not a client-built string.
  6. `SpectatorPage`: `ActionInput` renders in its read-only/hidden state (already partially built) and never calls `useTurnStream`.
  7. `useNotifications`: a mocked `your_turn` event for the current participant enables the action input; an event for a *different* participant does not.
  8. Multiplayer turn-order UI: given `usePlaythrough` data where it is *not* the current participant's turn, `ActionInput` is disabled even before any notification arrives (RFC: "must not even be possible... to submit when it isn't their turn" — this is a frontend-derivable state, not solely notification-driven; needs a `whose_turn_is_it` computation mirroring TRS's `request_receiver` logic, likely exposed via `usePlaythrough`'s response or a small derived selector).

### 3.3. Project Structure & File Layout
- **Files filled in (previously empty):**
  - `apps/frontend/src/shared/lib/sse-client.ts`
  - `apps/frontend/src/shared/hooks/useSSE.ts`
  - `apps/frontend/src/features/play/hooks/useTurnStream.ts`
  - `apps/frontend/src/features/play/hooks/useNotifications.ts`
  - `apps/frontend/src/features/play/hooks/useSpectator.ts`
  - `apps/frontend/src/features/play/api/turns.api.ts`
  - `apps/frontend/src/features/play/api/share.api.ts`
  - `apps/frontend/src/features/play/components/SpectatorView/SpectatorView.tsx`
- **Files created:**
  - `apps/frontend/src/features/play/hooks/useTurns.ts`
  - `apps/frontend/src/features/play/pages/SpectatorPage.tsx`
  - `apps/frontend/src/features/play/pages/JoinPage.tsx`
  - Test files mirroring each above under matching `__tests__`/`.test.tsx` conventions already used in the repo (confirm convention during implementation — no existing frontend test files were found, so this spec also establishes the first one; follow RTL + `msw` setup patterns from `apps/frontend`'s existing `package.json` devDependencies).
- **Files modified:**
  - `apps/frontend/src/features/play/stores/play.store.ts` — remove `simulateTokenStream` dependency; keep only client-only state.
  - `apps/frontend/src/features/play/pages/PlayPage.tsx` — wire `usePlaythroughTurns`, `useNotifications`.
  - `apps/frontend/src/features/play/components/PlayScreen/ActionInput.tsx` — call `useTurnStream` directly.
  - `apps/frontend/src/features/play/components/PlayScreen/SharePlaythroughModal.tsx` — real `share.api.ts` calls.
  - `apps/frontend/src/app/router.tsx` — add `/spectate/:id`, `/join` routes.
  - `apps/frontend/src/features/play/mock/playthroughMock.ts` — strip `simulateTokenStream`/`INITIAL_MOCK_PLAYTHROUGH` usage from production code paths (keep only if repurposed as isolated dev fixtures, not imported by `play.store.ts`).

### 3.4. Code Style & Interfaces

**`shared/lib/sse-client.ts`:**
```typescript
export interface SSEHandlers {
  onEvent: (eventName: string, data: string) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
}

export function createGetSSEConnection(url: string, handlers: SSEHandlers): () => void {
  const source = new EventSource(url, { withCredentials: true });
  const eventNames = ["narration", "done", "degraded", "your_turn", "participant_joined", "playthrough_ended"];
  eventNames.forEach((name) =>
    source.addEventListener(name, (e) => handlers.onEvent(name, (e as MessageEvent).data)),
  );
  source.onerror = (e) => handlers.onError?.(e);
  source.onopen = () => handlers.onOpen?.();
  return () => source.close();
}

export function createPostSSEConnection(
  url: string,
  body: unknown,
  token: string,
  handlers: SSEHandlers,
): () => void {
  const controller = new AbortController();
  void _streamPost(url, body, token, handlers, controller.signal);
  return () => controller.abort();
}

async function _streamPost(
  url: string,
  body: unknown,
  token: string,
  handlers: SSEHandlers,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });
    buffer = _consumeSSEFrames(buffer, handlers);
  }
}
```
`_consumeSSEFrames` is a separate pure function parsing complete `event:`/`data:` blocks out of `buffer` and returning the remainder — kept outside `_streamPost` per CLAUDE.md's single-responsibility rule (I/O loop vs. parsing are different concerns).

**`features/play/hooks/useTurnStream.ts`:**
```typescript
import { useCallback, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { createPostSSEConnection } from "@/shared/lib/sse-client";
import { useAuthStore } from "@/features/auth/stores/auth.store";
import { usePlayStore } from "../stores/play.store";

export function useTurnStream(playthroughId: string, participantId: string) {
  const queryClient = useQueryClient();
  const cancelRef = useRef<(() => void) | null>(null);
  const appendChunk = usePlayStore((s) => s.appendStreamingChunk);
  const setNarrating = usePlayStore((s) => s.setNarrating);

  const start = useCallback(
    (actionText: string) => {
      const token = useAuthStore.getState().accessToken;
      setNarrating(true);
      cancelRef.current = createPostSSEConnection(
        `${import.meta.env.VITE_TRS_URL}/v1/turn`,
        { playthrough_id: playthroughId, participant_id: participantId, action_text: actionText },
        token ?? "",
        {
          onEvent: (name, data) => {
            if (name === "narration") appendChunk(data);
            if (name === "done") {
              setNarrating(false);
              void queryClient.invalidateQueries({ queryKey: ["playthrough-turns", playthroughId] });
            }
            if (name === "degraded") setNarrating(false); // + toast, wired in ActionInput/PlayScreen
          },
        },
      );
    },
    [playthroughId, participantId, appendChunk, setNarrating, queryClient],
  );

  const stop = useCallback(() => cancelRef.current?.(), []);
  return { start, stop };
}
```

**`features/play/api/turns.api.ts`:**
```typescript
import { apiClient } from "@/shared/lib/api-client";
import { TurnLogItem } from "../types/play.types";

export interface GetTurnsParams {
  page?: number;
  page_size?: number;
  from_turn?: number;
}

export interface TurnsResponse {
  items: TurnLogItem[];
  total_count: number;
}

export async function getTurns(
  playthroughId: string,
  params: GetTurnsParams = {},
): Promise<TurnsResponse> {
  const { data } = await apiClient.get<TurnsResponse>(
    `/v1/playthroughs/${playthroughId}/turns`,
    { params },
  );
  return data;
}
```

### 3.5. Git & Review Workflow
- **Branch name:** `feat/play-screen-live-integration`
- **Commit scope:** `sse-client.ts` + `useSSE.ts` foundation as one commit (nothing else can build on top without these), then `useTurnStream`/`ActionInput`/`play.store` real-submission wiring, then history (`turns.api.ts`/`useTurns.ts`/`PlayPage`), then share/join, then spectate + notifications — each independently reviewable and testable.
- **PR validation checklist:**
  - [ ] `grep -r "new EventSource" apps/frontend/src` returns only `shared/lib/sse-client.ts`
  - [ ] `grep -r "simulateTokenStream" apps/frontend/src/features/play/stores` returns nothing
  - [ ] `npx tsc --noEmit` clean, no `any`
  - [ ] Manual verification steps in §3.1 pass against the real TRS/Core API from the two backend specs

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** route every SSE connection (GET or POST-streamed) through `shared/lib/sse-client.ts`; keep turn history as React Query server state, never duplicated into Zustand; disable `ActionInput` both from computed turn-order state and from live `your_turn` notifications (defense in depth, matching the RFC's frontend+backend enforcement model).
- ⚠️ **Ask First:** the exact `whose_turn_is_it` derivation on the frontend (test case 8) — needs `usePlaythrough`'s response to expose enough (`participants` list + `turn_count`) to compute this client-side; confirm the Core API `GET /v1/playthroughs/{id}` response shape includes participant `turn_order_position` data before building this, since `PlaythroughResponse` today does not include a participants list.
- 🚫 **Never:** buffer the full narration response before rendering any of it (mirrors the backend's own streaming rule); let `SpectatorPage` render an `ActionInput` capable of submitting.

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Network drop mid-stream:** `createPostSSEConnection`'s `fetch` throws/aborts; `useTurnStream` should catch this and behave like a `degraded` event (clear `is_narrating`, toast an error) rather than leaving the UI stuck showing a spinner forever.
- **Player navigates away mid-stream:** `useTurnStream`'s cleanup (`stop()`/`AbortController.abort()`) must fire on unmount so the fetch doesn't keep running against an unmounted component.
- **Spectator's `spectate` connection opens after the playthrough already ended:** the connection should still open successfully and simply receive no further events (or the backend closes it) — no special frontend handling beyond normal SSE `onerror`/close behavior.
- **Join link reused by someone already a participant:** Core API's `join_playthrough` (per the sharing spec) should be idempotent-friendly or return a clear error; frontend `JoinPage` should redirect straight to `/play/:id` if the join call fails with "already a participant" rather than showing a hard error (exact error contract to confirm with the backend spec's implementation).

## 5. Phased Implementation Tasks (Task Checklist)
- [x] **Task 1 (SSE foundation):** `shared/lib/sse-client.ts`, `shared/hooks/useSSE.ts`. **Design change from the original spec:** both GET and POST connections use `fetch()`'s streaming body, not the browser's native `EventSource` — `EventSource` cannot send a custom `Authorization` header, and this app's auth (both Core API and TRS) is Bearer-JWT-based, not cookie-based, so it could never have authenticated to `GET /v1/session/{id}/notifications`. One fetch-based mechanism for both GET and POST also keeps the SSE-frame parser single-sourced.
- [x] **Task 2 (Real turn submission):** `useTurnStream.ts`, `ActionInput.tsx`, `play.store.ts`. Kept the actual SSE orchestration in the store (not the hook) since `retryLastTurn`/`editLastAction` are plain store actions, not components, and need to re-trigger a submission too; `useTurnStream` is the thin component-facing entrypoint `ActionInput` calls. Deleted `mock/playthroughMock.ts` (`simulateTokenStream` and the fixture data) — nothing referenced it once `play.store.ts` no longer did.
- [x] **Task 3 (Turn history):** `turns.api.ts`, `useTurns.ts`, `PlayPage.tsx` wiring — real history now loads via `GET /v1/playthroughs/{id}/turns` instead of a hardcoded `[]`.
- [x] **Task 4 (Share + Join):** `share.api.ts`, `SharePlaythroughModal.tsx` (now calls the real endpoint for both link types instead of building URLs client-side), `JoinPage.tsx` + `useJoinPlaythrough.ts`, router registration.
- [x] **Task 5 (Spectate):** `useSpectator.ts`, `SpectatorView.tsx`, `SpectatorPage.tsx`, router registration.
- [x] **Task 6 (Multiplayer notifications + turn-order UI):** `useNotifications.ts`; `whose_turn_is_it` resolved by adding `participant_id` and a `participants` list to Core API's `PlaythroughResponse` (backend gap found during this task — the RFC's turn endpoint needs `participant_id` and nothing exposed it) and computing `can_act` in `PlayPage.tsx`; `ActionInput.tsx` now shows a distinct "waiting for the other player's turn" state, separate from the spectator state.
- [x] **Task 7 (Regression):** `npx tsc --noEmit` and `npm run build` clean. Full manual browser walkthrough performed with Playwright against the real running stack (Core API, TRS, Vite dev server) — not skipped. **Two real bugs found and fixed by this walkthrough, neither catchable by tsc/build:**
  1. **TRS had no CORS middleware** — it never needed one before this spec gave it a real HTTP entrypoint browsers call directly. The browser's preflight `OPTIONS /v1/turn` was rejected outright. Fixed by adding `CORSMiddleware` to `apps/turn-resolution-service/app/main.py`, mirroring Core API's existing setup.
  2. **A stream that closes without a `done`/`degraded` event left the UI hung on "AI Narrator Thinking..." forever** — reproduced live: TRS's Gemini call failed for a reason `ai_orchestrator.py` doesn't catch (missing local Vertex AI credentials, itself out of scope), the exception propagated out of the SSE generator, and the connection closed without emitting any terminal event. The frontend's `onError` only covered outright fetch failures, not this clean-but-incomplete close. Fixed by adding an `onClose` handler to `sse-client.ts`, and having `play.store.ts` treat "connection closed without ever seeing done/degraded" as a failure — the player now sees an actionable error message instead of an infinite spinner.
  - Spectate flow verified live end-to-end through a real generated share link: `GET /v1/playthroughs/{id}/turns?share_token=...` and `GET /v1/session/{id}/spectate?share_token=...` both returned 200 in the browser.
  - No two-browser multiplayer session was run live (would need a second seeded participant + real Gemini credentials to reach a completed turn) — turn-order gating and the notification wiring were verified via the TRS/Core API test suites (`test_pipeline.py`'s multiplayer notification test, `test_request_receiver.py`'s turn-order tests) instead.
