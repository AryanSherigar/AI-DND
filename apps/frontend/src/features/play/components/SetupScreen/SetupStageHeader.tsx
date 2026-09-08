import React from "react";

interface SetupStageHeaderProps {
  title?: string;
}

export const SetupStageHeader: React.FC<SetupStageHeaderProps> = ({
  title,
}) => (
  <div className="text-center space-y-3 pb-6 border-b border-zinc-800/60">
    <div className="flex items-center justify-center gap-2">
      <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-amber-500/90 bg-amber-500/10 px-3 py-1 rounded-full border border-amber-500/20">
        CAMPAIGN INITIATION
      </span>
    </div>

    <h1 className="font-serif text-3xl sm:text-4xl font-bold text-zinc-100 tracking-wide">
      {title || "Scenario Setup"}
    </h1>

    <p className="font-mono text-xs text-zinc-400 max-w-md mx-auto">
      Craft your starting parameters before the AI Narrator weaves your fate.
    </p>
  </div>
);
