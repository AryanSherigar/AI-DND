import { useEffect } from "react";
import { TurnLogResponse } from "../../api/turns.api";
import { resolveNarrationFont } from "@/shared/constants/narration-fonts";
import { loadNarrationFont } from "@/shared/lib/font-loader";

export interface SpectatorViewProps {
  scenarioTitle: string;
  turns: TurnLogResponse[];
  streamingText: string;
  streamingImageUrl?: string | null;
  isLive: boolean;
  narrationFont?: string | null;
}

interface SpectatorHeaderProps {
  scenarioTitle: string;
  isLive: boolean;
}

function SpectatorHeader({ scenarioTitle, isLive }: SpectatorHeaderProps) {
  return (
    <header className="border-b border-stone-800/60 px-6 py-4 flex items-center justify-between">
      <div>
        <h1 className="font-serif text-lg font-semibold text-amber-200">
          {scenarioTitle}
        </h1>
        <p className="font-mono text-[11px] text-stone-500 uppercase tracking-wider">
          Spectating (Read-Only)
        </p>
      </div>
      {isLive && (
        <span className="flex items-center gap-1.5 font-mono text-[11px] text-amber-400 uppercase tracking-wider">
          <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
          Live
        </span>
      )}
    </header>
  );
}

interface SpectatorTurnRowProps {
  turn: TurnLogResponse;
  fontClass: string;
}

function SpectatorTurnRow({ turn, fontClass }: SpectatorTurnRowProps) {
  return (
    <div className="space-y-2">
      <p className="font-serif italic text-stone-300 text-sm bg-stone-900/40 p-3 rounded-lg">
        "{turn.action_text}"
      </p>
      {turn.narration_text && (
        <p
          className={`${fontClass} text-stone-100 text-[15px] leading-relaxed`}
        >
          {turn.narration_text}
        </p>
      )}
    </div>
  );
}

export function SpectatorView({
  scenarioTitle,
  turns,
  streamingText,
  streamingImageUrl,
  isLive,
  narrationFont,
}: SpectatorViewProps) {
  const activeFont = resolveNarrationFont(narrationFont);

  useEffect(() => {
    loadNarrationFont(activeFont.id);
  }, [activeFont.id]);

  return (
    <div className="min-h-screen w-full bg-stone-950 text-stone-100 flex flex-col">
      <SpectatorHeader scenarioTitle={scenarioTitle} isLive={isLive} />

      <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-6 max-w-3xl mx-auto w-full">
        {turns.length === 0 && !streamingText && (
          <p className="text-stone-500 italic text-sm text-center py-12">
            No turns recorded yet.
          </p>
        )}

        {turns.map((turn) => (
          <SpectatorTurnRow
            key={turn.turn_id}
            turn={turn}
            fontClass={activeFont.fontClass}
          />
        ))}

        {streamingImageUrl && (
          <img
            src={streamingImageUrl}
            alt="Scene depiction"
            className="w-full rounded-lg border border-stone-800/60"
          />
        )}

        {streamingText && (
          <p
            className={`${activeFont.fontClass} text-stone-100 text-[15px] leading-relaxed`}
          >
            {streamingText}
            <span className="inline-block w-2 h-4 ml-1 bg-amber-400 animate-pulse align-middle" />
          </p>
        )}
      </div>
    </div>
  );
}
