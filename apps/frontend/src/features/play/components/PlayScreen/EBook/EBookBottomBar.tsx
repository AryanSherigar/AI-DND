import { usePlayStore } from "../../../stores/play.store";
import { EBookBottomBarProps } from "./ebook.types";

export function EBookBottomBar({
  isNarrating,
  isSpectator,
  hasTurns,
  onTakeAction,
  onContinue,
  onRetry,
  onEditAction,
  onOpenCodex,
}: EBookBottomBarProps) {
  const theme = usePlayStore((s) => s.ebook_theme);
  const isSepia = theme === "antique-sepia";

  const barStyle = isSepia
    ? "bg-[#faf4e8]/95 border-[#d8c7a8] text-[#2c2217] shadow-xl shadow-amber-900/10"
    : "bg-black/85 border-zinc-800/90 text-zinc-200 shadow-2xl shadow-black";

  const primaryBtnStyle = isSepia
    ? "bg-[#2c2217] hover:bg-[#433523] text-[#faf4e8]"
    : "bg-zinc-100 hover:bg-white text-zinc-950";

  if (isSpectator) {
    return (
      <footer className="fixed bottom-4 left-1/2 -translate-x-1/2 z-30 px-4 w-full max-w-lg opacity-60 hover:opacity-100 transition-opacity duration-300">
        <div
          className={`p-3 rounded-full border text-center font-mono text-xs backdrop-blur-md ${barStyle}`}
        >
          You are currently spectating this chronicle (Read-Only)
        </div>
      </footer>
    );
  }

  return (
    <footer className="fixed bottom-4 left-1/2 -translate-x-1/2 z-30 px-4 w-full max-w-2xl opacity-45 hover:opacity-100 focus-within:opacity-100 transition-opacity duration-300 group">
      <nav
        aria-label="Reading Controls"
        className={`flex items-center justify-between gap-2 p-2 sm:p-2.5 rounded-2xl border backdrop-blur-md ${barStyle}`}
      >
        <div className="flex items-center gap-1.5 sm:gap-2">
          <button
            type="button"
            disabled={isNarrating}
            onClick={onTakeAction}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl font-mono text-xs font-bold transition-all shadow-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${primaryBtnStyle}`}
          >
            <span>✍</span>
            <span>Take Action</span>
          </button>

          <button
            type="button"
            disabled={isNarrating}
            onClick={onContinue}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-inherit/25 hover:bg-zinc-800/50 font-mono text-xs font-medium transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            title="Prompt the narrator to continue the scene"
          >
            <span>Continue</span>
            <span>→</span>
          </button>
        </div>

        <div className="flex items-center gap-1">
          {hasTurns && !isNarrating && (
            <>
              <button
                type="button"
                onClick={onRetry}
                className="p-2 rounded-xl hover:bg-zinc-800/50 text-xs font-mono transition-colors opacity-75 hover:opacity-100 cursor-pointer"
                title="Retry Narrator Turn"
              >
                ↺ Retry
              </button>
              <button
                type="button"
                onClick={onEditAction}
                className="p-2 rounded-xl hover:bg-zinc-800/50 text-xs font-mono transition-colors opacity-75 hover:opacity-100 cursor-pointer"
                title="Edit Last Action"
              >
                ✎ Edit
              </button>
            </>
          )}

          <button
            type="button"
            onClick={onOpenCodex}
            className="p-2 px-2.5 rounded-xl border border-inherit/20 hover:bg-zinc-800/50 text-xs font-mono transition-colors opacity-75 hover:opacity-100 cursor-pointer"
            title="Open World Codex"
          >
            📖
          </button>
        </div>
      </nav>
    </footer>
  );
}
