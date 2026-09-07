# ADR-11: `_commitStreamedTurn` invalidates the `playthrough` query on every turn, not just at playthrough-end

**Status:** Accepted

## Context

The frontend's play store (`apps/frontend/src/features/play/stores/play.store.ts`) applies some turn effects locally before the server round-trip settles — most notably the `turn_summary` SSE event handler, which patches `playthrough.active_conditions` directly onto the store the moment it arrives (mid-stream, before `"done"`).

`PlayPage.tsx` independently rebuilds the entire `playthrough` object passed to `setPlaythrough` on every change to either the `["playthrough", id]` query (`serverPlaythrough`) or the `["playthrough-turns", id]` query (`turnsData`):

```tsx
useEffect(() => {
  if (!serverPlaythrough) return;
  const playthroughData =
    mode === "master"
      ? buildMasterPlaythroughData(serverPlaythrough, turnsData, isSpectatorMode)
      : buildNewbiePlaythroughData(serverPlaythrough, turnsData, isSpectatorMode);
  setPlaythrough(playthroughData);
}, [serverPlaythrough, turnsData, isSpectatorMode, setPlaythrough]);
```

`buildMasterPlaythroughData`/`buildNewbiePlaythroughData` derive `active_conditions`, player stats, and inventory purely from `serverPlaythrough.state` — never from the store's own locally-patched fields.

Previously, `_commitStreamedTurn` only invalidated `["playthrough", id]` when `pending_playthrough_ended` was set (i.e. the turn ended the playthrough); every ordinary turn invalidated `["playthrough-turns", id]` only. That refetch alone was enough to re-trigger `PlayPage`'s effect, which then rebuilt `playthroughData` from the *stale* `serverPlaythrough` snapshot — silently reverting the `active_conditions`/stat patch that had just been applied locally, until some unrelated event (an `isMyTurnSignal` notification, a manual navigation) happened to invalidate `["playthrough", id]` later.

## Decision

`_commitStreamedTurn` now invalidates `["playthrough", id]` unconditionally, alongside `["playthrough-turns", id]`, on every turn commit — not only when the playthrough ends. This mirrors the pattern the code already used for the end-of-game case.

## Consequences

- **One extra `GET /playthroughs/{id}` per turn.** Turns happen at conversational pace (the player reads narration, types an action, waits for streamed generation to finish) — this is not a hot path, and the added request is negligible against that cadence.
- **A residual race window, not a full elimination.** The two invalidated queries (`playthrough`, `playthrough-turns`) refetch independently and can resolve at different times. `PlayPage`'s effect can still fire once with fresh `turnsData` and a still-stale `serverPlaythrough` before firing again moments later once the `playthrough` refetch lands and self-corrects. In practice this window is on the order of tens to hundreds of milliseconds — short enough to be unlikely to be visibly noticed during normal play, but it is a narrowing of the bug, not a structural fix that removes the possibility entirely.

## Alternatives considered

- **Merge-based reconciliation in `PlayPage`'s effect**, instead of a destructive overwrite: keep the store's locally-patched fields and merge server data into them rather than replacing the whole object. This would remove the race window entirely (no network round-trip to wait on), but requires explicitly defining which `PlaythroughData` fields are locally-owned versus server-owned and writing merge logic to match — real code and test surface for a race window that, with the always-invalidate fix, is already small. Rejected for this pass; worth revisiting if the residual race is ever observed to cause a visible flicker in practice.
