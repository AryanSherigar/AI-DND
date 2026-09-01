import { useNavigate } from "react-router-dom";
import { usePlayStore } from "../../stores/play.store";

export function PlayHeader() {
  const navigate = useNavigate();
  const playthrough = usePlayStore((s) => s.playthrough);
  const is_left_sidebar_open = usePlayStore((s) => s.is_left_sidebar_open);
  const is_right_sidebar_open = usePlayStore((s) => s.is_right_sidebar_open);
  const toggleLeftSidebar = usePlayStore((s) => s.toggleLeftSidebar);
  const toggleRightSidebar = usePlayStore((s) => s.toggleRightSidebar);
  const openShareModal = usePlayStore((s) => s.openShareModal);
  const openEndModal = usePlayStore((s) => s.openEndModal);

  if (!playthrough) return null;

  const totalTurns = playthrough.turns.length;

  return (
    <header className="sticky top-0 z-30 w-full h-14 bg-stone-950/95 border-b border-stone-800/60 backdrop-blur-md px-4 flex items-center justify-between">
      {/* Left: Back & Title & Codex Toggle */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate("/play")}
          className="p-1.5 rounded-md text-stone-400 hover:text-stone-200 hover:bg-stone-900 transition-colors flex items-center gap-1.5 font-mono text-xs cursor-pointer"
          title="Back to Discovery Feed"
        >
          <svg
            className="w-4 h-4 text-stone-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.75}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M10 19l-7-7m0 0l7-7m-7 7h18"
            />
          </svg>
          <span className="hidden sm:inline">Discovery</span>
        </button>

        <button
          onClick={toggleLeftSidebar}
          className={`p-1.5 px-2.5 rounded-md font-mono text-xs flex items-center gap-1.5 transition-colors cursor-pointer ${
            is_left_sidebar_open
              ? "bg-stone-800 text-stone-100 font-medium"
              : "bg-stone-900 text-stone-400 hover:text-stone-200"
          }`}
          title="Toggle World Codex"
        >
          <svg
            className="w-4 h-4 text-stone-400"
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
          <span className="hidden md:inline">Codex</span>
        </button>

        <div className="h-4 w-px bg-stone-800/60 hidden sm:block" />

        <div className="truncate">
          <h1 className="font-serif text-base font-semibold text-stone-100 truncate leading-tight">
            {playthrough.scenario_title}
          </h1>
          <div className="font-mono text-[11px] text-stone-400 hidden md:block">
            by {playthrough.creator_name}
          </div>
        </div>
      </div>

      {/* Center: Plain Text Counter & Status Badge */}
      <div className="hidden md:flex items-center gap-3">
        <div className="flex items-center gap-1.5 font-mono text-xs text-stone-400">
          <svg
            className="w-4 h-4 text-stone-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.75}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span>
            {totalTurns} {totalTurns === 1 ? "Turn" : "Turns"}
          </span>
        </div>

        <span className="px-2.5 py-0.5 rounded-full bg-emerald-950/40 border border-emerald-800/40 text-emerald-400 font-mono text-[11px] flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Auto-saved
        </span>
      </div>

      {/* Right: Share, End & Character Toggle */}
      <div className="flex items-center gap-2">
        <button
          onClick={openShareModal}
          className="p-1.5 px-2.5 rounded-md bg-stone-900 hover:bg-stone-800 text-stone-300 font-mono text-xs flex items-center gap-1.5 transition-colors cursor-pointer"
          title="Share session"
        >
          <svg
            className="w-4 h-4 text-stone-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.75}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
            />
          </svg>
          <span className="hidden sm:inline">Share</span>
        </button>

        <button
          onClick={openEndModal}
          className="p-1.5 px-2.5 rounded-md bg-stone-900 hover:bg-stone-800 text-stone-300 font-mono text-xs flex items-center gap-1 transition-colors cursor-pointer"
          title="End Playthrough"
        >
          <span>End</span>
        </button>

        <button
          onClick={toggleRightSidebar}
          className={`p-1.5 px-2.5 rounded-md font-mono text-xs flex items-center gap-1.5 transition-colors cursor-pointer ${
            is_right_sidebar_open
              ? "bg-stone-800 text-stone-100 font-medium"
              : "bg-stone-900 text-stone-400 hover:text-stone-200"
          }`}
          title="Toggle Character Sheet"
        >
          <svg
            className="w-4 h-4 text-stone-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.75}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
            />
          </svg>
          <span className="hidden md:inline">Character</span>
        </button>
      </div>
    </header>
  );
}
