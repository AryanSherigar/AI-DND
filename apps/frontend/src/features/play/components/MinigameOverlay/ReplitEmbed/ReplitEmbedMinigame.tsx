import { useEffect, useRef, useState } from "react";
import { useReplitHandshake } from "@/shared/hooks/useReplitHandshake";
import { IframeLoadingState } from "./IframeLoadingState";
import { ReplitEmbedMinigameProps } from "./ReplitEmbedMinigame.types";

// NOTE: allow-same-origin is deliberately omitted. Combined with
// allow-scripts it would let the framed (creator-supplied, untrusted) origin
// keep full script + storage access to itself, defeating the sandbox. See
// useReplitHandshake.ts for the corresponding opaque-origin postMessage check
// this requires.
const REPLIT_IFRAME_SANDBOX = "allow-scripts allow-forms";

/**
 * Live-embeds a creator's Replit-hosted minigame in a sandboxed iframe and
 * resolves via the shared postMessage handshake (useReplitHandshake). Allows
 * exactly one manual retry after a handshake timeout — a second timeout
 * auto-resolves to {outcome_tag: "timeout"} so the turn is never stuck
 * waiting on an unreachable/broken Repl (docs/specs/master-mode-minigames
 * .spec.md §2 sequence flow, step 7; §4 "Replit URL becomes unreachable").
 */
export function ReplitEmbedMinigame({
  replitEmbedUrl,
  timeoutSeconds,
  onComplete,
}: ReplitEmbedMinigameProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const hasResolvedRef = useRef(false);
  // Mirrors hasRetried below, but read inside the timed-out effect instead
  // of listed as its dependency: the effect must only re-evaluate when
  // `status` itself transitions, not on the same render pass where a retry
  // click flips hasRetried but the hook's own status hasn't caught up to
  // "waiting" yet — depending on hasRetried directly caused a false-positive
  // auto-resolve immediately after clicking Retry.
  const hasRetriedRef = useRef(false);
  const [hasRetried, setHasRetried] = useState(false);

  const { status, outcome, attempt, retry } = useReplitHandshake(
    iframeRef,
    replitEmbedUrl,
    timeoutSeconds * 1000,
  );

  useEffect(() => {
    if (!outcome || hasResolvedRef.current) return;
    hasResolvedRef.current = true;
    onComplete({ outcome_tag: outcome.outcome_tag, score: outcome.score });
  }, [outcome, onComplete]);

  useEffect(() => {
    // Only one manual retry is allowed (locked design) — a second timeout,
    // after the player has already retried once, auto-resolves the turn.
    if (
      status !== "timed_out" ||
      hasResolvedRef.current ||
      !hasRetriedRef.current
    ) {
      return;
    }
    hasResolvedRef.current = true;
    onComplete({ outcome_tag: "timeout" });
  }, [status, onComplete]);

  const handleRetry = (): void => {
    hasRetriedRef.current = true;
    setHasRetried(true);
    retry();
  };

  const canRetry = status === "timed_out" && !hasRetried;

  return (
    <div className="relative w-full h-full max-w-4xl max-h-[80vh] aspect-video">
      <iframe
        key={attempt}
        ref={iframeRef}
        src={replitEmbedUrl}
        sandbox={REPLIT_IFRAME_SANDBOX}
        className="w-full h-full border-0"
        title="Minigame challenge"
      />
      {status !== "ready" && (
        <IframeLoadingState
          isTimedOut={status === "timed_out"}
          canRetry={canRetry}
          onRetry={handleRetry}
        />
      )}
    </div>
  );
}
