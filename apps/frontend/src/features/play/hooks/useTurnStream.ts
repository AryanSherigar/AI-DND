import { usePlayStore } from "../stores/play.store";

/**
 * Submits a player action to TRS and streams back narration.
 *
 * The actual SSE plumbing lives in play.store.ts (via shared/lib/sse-client.ts)
 * rather than here, because retryLastTurn/editLastAction — plain store
 * actions, not React components — need to re-trigger a submission too. This
 * hook is the component-facing entrypoint components should call.
 */
export function useTurnStream() {
  const start = usePlayStore((s) => s.submitTurn);
  const stop = usePlayStore((s) => s.stopGeneration);
  return { start, stop };
}
