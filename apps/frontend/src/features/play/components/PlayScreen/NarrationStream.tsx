import { ReactNode } from "react";
import { usePlayStore } from "../../stores/play.store";

const MODE_ICONS: Record<string, ReactNode> = {
  say: (
    <svg
      className="w-3.5 h-3.5"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.75}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
      />
    </svg>
  ),
  do: (
    <svg
      className="w-3.5 h-3.5"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.75}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M13 10V3L4 14h7v7l9-11h-7z"
      />
    </svg>
  ),
  story: (
    <svg
      className="w-3.5 h-3.5"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.75}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
      />
    </svg>
  ),
  see: (
    <svg
      className="w-3.5 h-3.5"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.75}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
      />
    </svg>
  ),
};

export function NarrationStream() {
  const is_narrating = usePlayStore((s) => s.is_narrating);
  const streaming_text = usePlayStore((s) => s.streaming_text);
  const last_submitted_action = usePlayStore((s) => s.last_submitted_action);
  const active_mode = usePlayStore((s) => s.active_mode);
  const characterName = usePlayStore(
    (s) => s.playthrough?.character_name ?? "Player",
  );
  const stopGeneration = usePlayStore((s) => s.stopGeneration);

  if (!is_narrating) return null;

  return (
    <div className="space-y-6 py-6 animate-fade-in">
      {/* Player Action Preview */}
      <div className="flex items-start gap-3">
        <div className="w-7 h-7 rounded-full bg-stone-900 border border-stone-800/60 flex items-center justify-center text-stone-400 shrink-0 mt-0.5">
          {MODE_ICONS[active_mode] || MODE_ICONS.do}
        </div>
        <div className="flex-1 space-y-1.5">
          <div className="flex items-center gap-2 font-mono text-[11px]">
            <span className="text-stone-300 font-semibold">
              {characterName}
            </span>
            <span className="px-2 py-0.5 rounded-full bg-stone-900 border border-stone-800/40 text-stone-400 uppercase text-[10px] tracking-wider">
              {active_mode}
            </span>
          </div>
          <p className="font-serif italic text-stone-200 text-[15px] leading-relaxed bg-stone-900/40 p-3.5 rounded-lg">
            "{last_submitted_action}"
          </p>
        </div>
      </div>

      {/* Live Streaming Narration */}
      <div className="flex items-start gap-3">
        <div className="w-7 h-7 rounded-full bg-stone-900 border border-stone-700 flex items-center justify-center text-stone-300 shrink-0 mt-1">
          <svg
            className="w-3.5 h-3.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.75}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
            />
          </svg>
        </div>
        <div className="flex-1 space-y-2">
          <div className="flex items-center justify-between">
            <div className="font-mono text-[11px] uppercase text-stone-400 tracking-wider flex items-center gap-2 font-medium">
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
              <span>AI Narrator Thinking...</span>
            </div>
            <button
              type="button"
              onClick={stopGeneration}
              className="px-2.5 py-1 rounded bg-stone-900 hover:bg-stone-800 border border-red-900/40 text-red-400 font-mono text-[10px] transition-colors cursor-pointer"
            >
              Stop Generation
            </button>
          </div>
          <div className="font-serif text-stone-100 text-[15px] leading-relaxed space-y-3">
            {streaming_text ? (
              <p>
                {streaming_text}
                <span className="inline-block w-2 h-4 ml-1 bg-amber-400 animate-pulse align-middle" />
              </p>
            ) : (
              <p className="italic text-stone-500 text-sm">
                Formulating narrative response...
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
