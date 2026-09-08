import { usePlayStore } from "../../stores/play.store";
import { useMinigameResult } from "../../hooks/useMinigameResult";
import { MinigameOutcomeResult } from "./MinigameOverlay.types";
import { ReplitEmbedMinigame } from "./ReplitEmbed/ReplitEmbedMinigame";
import { DodgeMinigame } from "./DodgeMinigame/DodgeMinigame";

/**
 * Full-screen takeover for a triggered minigame. Reads active_minigame from
 * play.store.ts directly (set either by a fresh "minigame" SSE event or,
 * on reload, from PlaythroughData.pending_minigame) and renders nothing
 * when none is pending — safe to mount unconditionally on the play surface.
 *
 * No AI narration happens while this is showing (locked design,
 * docs/specs/master-mode-minigames.spec.md §2 step 6): both minigame kinds
 * resolve locally, then hand their outcome to onResolve. The overlay remains
 * mounted until the server confirms the result, so a failed submission can be
 * retried without losing the completed encounter.
 */
export function MinigameOverlay() {
  const activeMinigame = usePlayStore((s) => s.active_minigame);
  const pendingResult = usePlayStore((s) => s.pending_minigame_result);
  const { submit, retry, submitTimeoutFallback } = useMinigameResult();

  if (!activeMinigame) return null;

  const handleResolve = (result: MinigameOutcomeResult): void => {
    submit({
      minigame_id: activeMinigame.minigame_id,
      attempt_id: activeMinigame.attempt_id,
      ...result,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black">
      {activeMinigame.minigame_type === "dodge" &&
        activeMinigame.dodge_config && (
          <DodgeMinigame
            dodgeConfig={activeMinigame.dodge_config}
            onComplete={handleResolve}
          />
        )}
      {activeMinigame.minigame_type === "replit_embed" &&
        activeMinigame.replit_embed_url && (
          <ReplitEmbedMinigame
            replitEmbedUrl={activeMinigame.replit_embed_url}
            timeoutSeconds={activeMinigame.timeout_seconds}
            onComplete={handleResolve}
          />
        )}
      {pendingResult && (
        <div
          className="absolute inset-0 flex items-center justify-center bg-black/80 p-6 text-center text-white"
          role="status"
          aria-live="assertive"
        >
          <div className="max-w-md space-y-4 rounded border border-white/30 bg-zinc-950 p-6">
            <p className="font-semibold">
              {pendingResult.status === "reconciling"
                ? "Checking the server…"
                : pendingResult.status === "submitting"
                ? "Saving your result…"
                : pendingResult.status === "retryable"
                  ? "We could not save your result."
                  : "Result saving timed out."}
            </p>
            <p className="text-sm text-zinc-300">
              {pendingResult.status === "terminal"
                ? "Your encounter remains open. Resolve it safely as a timeout, or reload to reconcile with the server."
                : "Your completed result is retained and will not be lost."}
            </p>
            {pendingResult.status === "retryable" && (
              <button
                type="button"
                className="rounded bg-white px-4 py-2 text-black"
                onClick={retry}
              >
                Retry save
              </button>
            )}
            {pendingResult.status === "terminal" && (
              <button
                type="button"
                className="rounded bg-white px-4 py-2 text-black"
                onClick={submitTimeoutFallback}
              >
                Resolve as timeout
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
