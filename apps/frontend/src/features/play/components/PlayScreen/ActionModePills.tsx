import { ReactNode } from "react";
import { ActionMode } from "../../types/play.types";
import { usePlayStore } from "../../stores/play.store";

interface ModeOption {
  key: ActionMode;
  label: string;
  hint: string;
  icon: ReactNode;
}

const MODES: ModeOption[] = [
  {
    key: "say",
    label: "Say",
    hint: "Direct character speech & dialogue",
    icon: (
      <svg
        className="w-4 h-4"
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
  },
  {
    key: "do",
    label: "Do",
    hint: "Physical action or movement",
    icon: (
      <svg
        className="w-4 h-4"
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
  },
  {
    key: "story",
    label: "Story",
    hint: "Direct narrative direction or environment shift",
    icon: (
      <svg
        className="w-4 h-4"
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
  },
  {
    key: "see",
    label: "See",
    hint: "Inspect surroundings, objects, or NPCs",
    icon: (
      <svg
        className="w-4 h-4"
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
  },
];

export function ActionModePills() {
  const active_mode = usePlayStore((s) => s.active_mode);
  const setActiveMode = usePlayStore((s) => s.setActiveMode);
  const is_narrating = usePlayStore((s) => s.is_narrating);

  return (
    <div className="flex items-center gap-1 p-1 bg-stone-900/60 rounded-lg font-mono text-xs mb-2">
      {MODES.map((mode) => {
        const isActive = active_mode === mode.key;
        return (
          <button
            key={mode.key}
            type="button"
            disabled={is_narrating}
            onClick={() => setActiveMode(mode.key)}
            title={mode.hint}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all cursor-pointer ${
              isActive
                ? "bg-amber-500 text-stone-950 font-semibold shadow-sm"
                : "text-stone-400 hover:text-stone-200 hover:bg-stone-800/40"
            } ${is_narrating ? "opacity-50 cursor-not-allowed" : ""}`}
          >
            <span className="shrink-0">{mode.icon}</span>
            <span>{mode.label}</span>
          </button>
        );
      })}
    </div>
  );
}
