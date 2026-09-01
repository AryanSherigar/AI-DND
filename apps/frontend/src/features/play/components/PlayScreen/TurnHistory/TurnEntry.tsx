import { ReactNode } from "react";
import { TurnLogItem } from "../../../types/play.types";
import { usePlayStore } from "../../../stores/play.store";

interface TurnEntryProps {
  turn: TurnLogItem;
  isLatest: boolean;
}

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

export function TurnEntry({ turn, isLatest }: TurnEntryProps) {
  const characterName = usePlayStore(
    (s) => s.playthrough?.character_name ?? "Player",
  );
  const is_narrating = usePlayStore((s) => s.is_narrating);
  const retryLastTurn = usePlayStore((s) => s.retryLastTurn);
  const editLastAction = usePlayStore((s) => s.editLastAction);

  return (
    <div className="space-y-6 py-6 border-b border-stone-900/60 last:border-0 group">
      {/* Player Action Block */}
      <div className="flex items-start gap-3">
        <div className="w-7 h-7 rounded-full bg-stone-900 border border-stone-800/60 flex items-center justify-center text-stone-400 shrink-0 mt-0.5">
          {MODE_ICONS[turn.action_mode] || MODE_ICONS.do}
        </div>
        <div className="flex-1 space-y-1.5">
          <div className="flex items-center gap-2 font-mono text-[11px]">
            <span className="text-stone-300 font-semibold">
              {characterName}
            </span>
            <span className="px-2 py-0.5 rounded-full bg-stone-900 border border-stone-800/40 text-stone-400 uppercase text-[10px] tracking-wider">
              {turn.action_mode}
            </span>
          </div>
          <p className="font-serif italic text-stone-200 text-[15px] leading-relaxed bg-stone-900/40 p-3.5 rounded-lg">
            "{turn.action_text}"
          </p>
        </div>
      </div>

      {/* AI Narration Block */}
      <div className="flex items-start gap-3">
        <div className="w-7 h-7 rounded-full bg-stone-900 border border-stone-800/60 flex items-center justify-center text-stone-400 shrink-0 mt-1">
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
          <div className="font-mono text-[11px] uppercase text-stone-400 tracking-wider font-medium">
            AI Narrator
          </div>
          <div className="font-serif text-stone-200 text-[15px] leading-relaxed space-y-3">
            {turn.narration_text.split("\n\n").map((paragraph, idx) => (
              <p key={idx}>{paragraph}</p>
            ))}
          </div>

          {/* Controls for latest turn */}
          {isLatest && !is_narrating && (
            <div className="flex items-center gap-2 pt-2 opacity-80 group-hover:opacity-100 transition-opacity">
              <button
                type="button"
                onClick={retryLastTurn}
                className="px-2.5 py-1 rounded bg-stone-900 hover:bg-stone-800 text-stone-300 font-mono text-[11px] flex items-center gap-1.5 transition-colors cursor-pointer"
                title="Re-generate AI narration for this action"
              >
                <svg
                  className="w-3 h-3 text-stone-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.75}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                </svg>
                Retry
              </button>
              <button
                type="button"
                onClick={editLastAction}
                className="px-2.5 py-1 rounded bg-stone-900 hover:bg-stone-800 text-stone-300 font-mono text-[11px] flex items-center gap-1.5 transition-colors cursor-pointer"
                title="Edit action text and replace turn"
              >
                <svg
                  className="w-3 h-3 text-stone-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.75}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                  />
                </svg>
                Edit Action
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
