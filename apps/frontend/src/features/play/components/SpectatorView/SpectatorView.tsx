import { TurnLogResponse } from "../../api/turns.api";

export interface SpectatorViewProps {
  scenarioTitle: string;
  turns: TurnLogResponse[];
  streamingText: string;
  isLive: boolean;
}

export function SpectatorView({
  scenarioTitle,
  turns,
  streamingText,
  isLive,
}: SpectatorViewProps) {
  return (
    <div className="min-h-screen w-full bg-stone-950 text-stone-100 flex flex-col">
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

      <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-6 max-w-3xl mx-auto w-full">
        {turns.length === 0 && !streamingText && (
          <p className="text-stone-500 italic text-sm text-center py-12">
            No turns recorded yet.
          </p>
        )}

        {turns.map((turn) => (
          <div key={turn.turn_id} className="space-y-2">
            <p className="font-serif italic text-stone-300 text-sm bg-stone-900/40 p-3 rounded-lg">
              "{turn.action_text}"
            </p>
            {turn.narration_text && (
              <p className="font-serif text-stone-100 text-[15px] leading-relaxed">
                {turn.narration_text}
              </p>
            )}
          </div>
        ))}

        {streamingText && (
          <p className="font-serif text-stone-100 text-[15px] leading-relaxed">
            {streamingText}
            <span className="inline-block w-2 h-4 ml-1 bg-amber-400 animate-pulse align-middle" />
          </p>
        )}
      </div>
    </div>
  );
}
