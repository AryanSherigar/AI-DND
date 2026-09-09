import { useState } from "react";
import { usePlayStore } from "../../stores/play.store";
import { useMinigameResult } from "../../hooks/useMinigameResult";
import { MinigameOutcomeResult } from "@/shared/types/minigame.types";
import { ReplitEmbedMinigame } from "@/shared/components/minigames/ReplitEmbed/ReplitEmbedMinigame";
import { DodgeMinigame } from "@/shared/components/minigames/DodgeMinigame/DodgeMinigame";
import { useDefaultMoodTracks } from "@/shared/hooks/useDefaultMoodTracks";
import { ForfeitConfirmModal } from "./ForfeitConfirmModal";

const PENDING_STATUS_TITLES: Record<string, string> = {
  reconciling: "Checking the server…",
  submitting: "Saving your result…",
  retryable: "We could not save your result.",
  terminal: "Result saving timed out.",
};

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
  const [isConfirmingForfeit, setIsConfirmingForfeit] = useState(false);
  const activeMinigame = usePlayStore((s) => s.active_minigame);
  const pendingResult = usePlayStore((s) => s.pending_minigame_result);
  const { submit, retry, submitTimeoutFallback } = useMinigameResult();
  const { data: defaultMoodTracks } = useDefaultMoodTracks();

  if (!activeMinigame) return null;

  const handleResolve = (result: MinigameOutcomeResult): void => {
    submit({
      minigame_id: activeMinigame.minigame_id,
      attempt_id: activeMinigame.attempt_id,
      ...result,
    });
  };

  const handleConfirmForfeit = (): void => {
    setIsConfirmingForfeit(false);
    handleResolve({ outcome_tag: "timeout" });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black">
      <div className="pointer-events-none absolute left-0 right-0 top-0 z-20 flex items-center justify-between bg-gradient-to-b from-black/80 to-transparent px-6 py-4">
        <div className="pointer-events-auto flex items-center gap-2">
          <span className="rounded bg-white/10 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-zinc-400">
            Challenge
          </span>
          <span className="text-sm font-medium text-white">
            {activeMinigame.label}
          </span>
        </div>
        <button
          type="button"
          onClick={() => setIsConfirmingForfeit(true)}
          className="pointer-events-auto rounded border border-white/20 bg-zinc-900/80 px-3 py-1 text-xs font-medium text-zinc-300 backdrop-blur transition-colors hover:bg-zinc-800 hover:text-white"
        >
          Forfeit
        </button>
      </div>

      {activeMinigame.minigame_type === "dodge" &&
        activeMinigame.dodge_config && (
          <DodgeMinigame
            dodgeConfig={activeMinigame.dodge_config}
            onComplete={handleResolve}
            tensionDefaultTrackUrl={defaultMoodTracks?.tension}
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

      <ForfeitConfirmModal
        isOpen={isConfirmingForfeit}
        onConfirm={handleConfirmForfeit}
        onCancel={() => setIsConfirmingForfeit(false)}
      />
      {pendingResult && (
        <div
          className="absolute inset-0 flex items-center justify-center bg-black/80 p-6 text-center text-white"
          role="status"
          aria-live="assertive"
        >
          <div className="max-w-md space-y-4 rounded border border-white/30 bg-zinc-950 p-6">
            <p className="font-semibold">
              {PENDING_STATUS_TITLES[pendingResult.status] ??
                "Result saving timed out."}
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
