import React, { useState } from "react";
import { DodgeMinigame } from "@/shared/components/minigames/DodgeMinigame/DodgeMinigame";
import { ReplitEmbedMinigame } from "@/shared/components/minigames/ReplitEmbed/ReplitEmbedMinigame";
import { MinigameOutcomeResult } from "../../types/minigame.types";
import { MinigamePreviewOverlayProps } from "./MinigamePreviewOverlay.types";

// Not authored per-minigame anywhere today — the real play-time value comes
// from TRS's own minigame_iframe_handshake_timeout_seconds config, which a
// Studio preview has no access to. 20s matches that service's default.
const PREVIEW_REPLIT_TIMEOUT_SECONDS = 20;

const describeOutcome = (
  outcomeTag: MinigameOutcomeResult["outcome_tag"],
): string => {
  if (outcomeTag === "win") return "Won";
  if (outcomeTag === "lose") return "Lost";
  return "Timed out";
};

/**
 * Full-screen preview of a minigame's current (possibly unsaved) form
 * config, launched from MinigameForm so a creator can see it play before
 * saving — without a real playthrough, trigger condition, or state
 * mutation. The result shown here is never submitted anywhere.
 */
export const MinigamePreviewOverlay: React.FC<MinigamePreviewOverlayProps> = ({
  minigameType,
  dodgeConfig,
  replitEmbedUrl,
  onClose,
}) => {
  const [result, setResult] = useState<MinigameOutcomeResult | null>(null);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black">
      <button
        type="button"
        onClick={onClose}
        className="absolute right-4 top-4 z-10 rounded-md bg-white/10 px-3 py-1.5 text-sm font-semibold text-white hover:bg-white/20"
      >
        Close preview
      </button>

      {!result && minigameType === "dodge" && (
        <DodgeMinigame dodgeConfig={dodgeConfig} onComplete={setResult} />
      )}
      {!result && minigameType === "replit_embed" && (
        <ReplitEmbedMinigame
          replitEmbedUrl={replitEmbedUrl}
          timeoutSeconds={PREVIEW_REPLIT_TIMEOUT_SECONDS}
          onComplete={setResult}
        />
      )}

      {result && (
        <div className="max-w-md space-y-4 rounded border border-white/30 bg-zinc-950 p-6 text-center text-white">
          <p className="text-lg font-semibold uppercase tracking-wide">
            {describeOutcome(result.outcome_tag)}
          </p>
          {result.score !== undefined && (
            <p className="text-sm text-zinc-300">Score: {result.score}</p>
          )}
          <p className="text-xs text-zinc-500">
            Preview only — nothing was saved or submitted.
          </p>
          <button
            type="button"
            onClick={onClose}
            className="rounded bg-white px-4 py-2 text-sm font-semibold text-black"
          >
            Done
          </button>
        </div>
      )}
    </div>
  );
};
