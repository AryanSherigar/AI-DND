import React from "react";

export const SetupStageEmptyState: React.FC = () => (
  <div className="text-center py-8 px-4 bg-zinc-900/40 border border-zinc-800/50 rounded-xl space-y-3">
    <div className="w-10 h-10 mx-auto rounded-full bg-zinc-800/60 flex items-center justify-center text-amber-400/80">
      <svg
        className="w-5 h-5"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
        />
      </svg>
    </div>
    <p className="font-serif text-sm text-zinc-300 italic">
      No character customization is required for this scenario.
    </p>
    <p className="font-mono text-xs text-zinc-500">
      The chronicle begins immediately upon departure.
    </p>
  </div>
);
