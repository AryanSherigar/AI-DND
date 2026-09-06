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
 * resolve locally, then hand their outcome to onResolve, which closes the
 * overlay immediately and submits the result — narration streams into the
 * normal view afterward, like any other turn.
 */
export function MinigameOverlay() {
  const activeMinigame = usePlayStore((s) => s.active_minigame);
  const { submit, clear } = useMinigameResult();

  if (!activeMinigame) return null;

  const handleResolve = (result: MinigameOutcomeResult): void => {
    clear();
    submit({ minigame_id: activeMinigame.minigame_id, ...result });
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
    </div>
  );
}
