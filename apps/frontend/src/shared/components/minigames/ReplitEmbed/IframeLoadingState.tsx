import { IframeLoadingStateProps } from "./IframeLoadingState.types";

/**
 * Presentational overlay shown above the sandboxed Replit iframe while
 * waiting for its "minigame:ready" handshake, and again if that handshake
 * times out (see useReplitHandshake / ReplitEmbedMinigame).
 */
export function IframeLoadingState({
  isTimedOut,
  canRetry,
  onRetry,
}: IframeLoadingStateProps) {
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-zinc-950/90 text-zinc-100">
      {!isTimedOut && (
        <>
          <div className="w-10 h-10 border-2 border-amber-500/30 border-t-amber-500 rounded-full animate-spin" />
          <p className="font-mono text-xs text-amber-500/80 tracking-widest uppercase">
            Connecting to the challenge...
          </p>
        </>
      )}
      {isTimedOut && (
        <>
          <p className="font-mono text-xs text-red-400 tracking-widest uppercase">
            The challenge did not respond in time.
          </p>
          {canRetry && (
            <button
              onClick={onRetry}
              className="border border-amber-500/50 px-4 py-2 text-xs font-mono uppercase tracking-widest text-amber-400 hover:bg-amber-500/10"
            >
              Retry
            </button>
          )}
        </>
      )}
    </div>
  );
}
