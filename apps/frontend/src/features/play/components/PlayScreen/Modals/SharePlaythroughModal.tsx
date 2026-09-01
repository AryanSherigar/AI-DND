import { useState } from "react";
import { usePlayStore } from "../../../stores/play.store";

export function SharePlaythroughModal() {
  const isOpen = usePlayStore((s) => s.is_share_modal_open);
  const closeModal = usePlayStore((s) => s.closeShareModal);
  const playthrough = usePlayStore((s) => s.playthrough);

  const [copiedType, setCopiedType] = useState<"spectate" | "join" | null>(
    null,
  );

  if (!isOpen || !playthrough) return null;

  const currentUrl = window.location.origin;
  const spectatorUrl = `${currentUrl}/play/${playthrough.playthrough_id}?mode=spectate`;
  const joinUrl = `${currentUrl}/play/${playthrough.playthrough_id}?mode=join`;

  const handleCopy = (url: string, type: "spectate" | "join") => {
    navigator.clipboard.writeText(url);
    setCopiedType(type);
    setTimeout(() => setCopiedType(null), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-stone-950 border border-amber-900/40 rounded-2xl p-6 shadow-2xl space-y-5 animate-scale-up">
        <div className="flex items-center justify-between border-b border-amber-900/20 pb-3">
          <div className="flex items-center gap-2">
            <svg
              className="w-5 h-5 text-amber-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
              />
            </svg>
            <h3 className="font-mono text-sm uppercase tracking-wider text-amber-200 font-bold">
              Share Playthrough
            </h3>
          </div>
          <button
            onClick={closeModal}
            className="text-stone-400 hover:text-stone-200 p-1 rounded hover:bg-stone-900"
          >
            ✕
          </button>
        </div>

        <div className="space-y-4">
          {/* Spectate Link */}
          <div className="space-y-1.5">
            <label className="font-mono text-xs text-amber-400/90 block">
              Spectator Link (Read-Only)
            </label>
            <div className="flex items-center gap-2">
              <input
                readOnly
                value={spectatorUrl}
                className="flex-1 bg-stone-900 text-stone-300 font-mono text-xs p-2.5 rounded border border-amber-900/30 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => handleCopy(spectatorUrl, "spectate")}
                className="px-3 py-2 bg-amber-500 hover:bg-amber-400 text-stone-950 font-mono text-xs font-bold rounded transition-colors cursor-pointer"
              >
                {copiedType === "spectate" ? "Copied!" : "Copy"}
              </button>
            </div>
          </div>

          {/* Join Link */}
          <div className="space-y-1.5">
            <label className="font-mono text-xs text-amber-400/90 block">
              Multiplayer Join Link
            </label>
            <div className="flex items-center gap-2">
              <input
                readOnly
                value={joinUrl}
                className="flex-1 bg-stone-900 text-stone-300 font-mono text-xs p-2.5 rounded border border-amber-900/30 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => handleCopy(joinUrl, "join")}
                className="px-3 py-2 bg-stone-800 hover:bg-stone-700 text-amber-300 font-mono text-xs rounded border border-amber-900/40 transition-colors cursor-pointer"
              >
                {copiedType === "join" ? "Copied!" : "Copy"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
