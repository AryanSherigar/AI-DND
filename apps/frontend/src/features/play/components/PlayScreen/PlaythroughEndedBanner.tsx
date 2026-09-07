interface PlaythroughEndedBannerProps {
  outcomeTag: "win" | "lose";
  outcomeTitle: string;
  outcomeText: string;
  onBackToLibrary: () => void;
}

export function PlaythroughEndedBanner({
  outcomeTag,
  outcomeTitle,
  outcomeText,
  onBackToLibrary,
}: PlaythroughEndedBannerProps) {
  const accentClass =
    outcomeTag === "win"
      ? "border-emerald-500/40 text-emerald-200"
      : "border-red-500/40 text-red-200";

  return (
    <div className="fixed inset-x-0 top-0 z-40 flex justify-center px-4 pt-4">
      <div
        role="alert"
        className={`w-full max-w-xl rounded-2xl border bg-black/90 backdrop-blur-md shadow-2xl p-5 text-center ${accentClass}`}
      >
        <p className="font-mono text-[10px] uppercase tracking-widest opacity-70 mb-1">
          {outcomeTag === "win" ? "Victory" : "Defeat"}
        </p>
        <h2 className="font-serif text-xl font-bold mb-2">{outcomeTitle}</h2>
        <p className="text-sm leading-relaxed text-zinc-300 mb-4">
          {outcomeText}
        </p>
        <button
          type="button"
          onClick={onBackToLibrary}
          className="px-4 py-2 rounded-xl border border-inherit/30 hover:bg-white/5 font-mono text-xs transition-colors cursor-pointer"
        >
          Return to Library
        </button>
      </div>
    </div>
  );
}
