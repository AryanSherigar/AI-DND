import { usePlayStore } from "../stores/play.store";

/**
 * Submits a resolved minigame outcome to TRS and dismisses the overlay.
 *
 * Mirrors useTurnStream: the actual SSE plumbing lives in play.store.ts
 * (submitMinigameResult reuses the same _startTurnStream machinery
 * submitTurn uses), this hook is just the component-facing entrypoint
 * MinigameOverlay/ReplitEmbedMinigame call.
 */
export function useMinigameResult() {
  const submit = usePlayStore((s) => s.submitMinigameResult);
  const retry = usePlayStore((s) => s.retryMinigameResult);
  const submitTimeoutFallback = usePlayStore((s) => s.submitMinigameTimeoutFallback);
  return { submit, retry, submitTimeoutFallback };
}
