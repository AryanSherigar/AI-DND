import { KeyboardEvent, useEffect, useRef, useState } from "react";
import { usePlayStore } from "../../stores/play.store";
import { useTurnStream } from "../../hooks/useTurnStream";
import { ActionModePills } from "./ActionModePills";

const PLACEHOLDERS: Record<string, string> = {
  say: 'Say: "Halt! Who goes there?"...',
  do: "Do: I raise my lantern and step into the cavern...",
  story: "Story: A heavy gust of wind blows through the trees...",
  see: "See: I inspect the mysterious runes carved into the archway...",
};

export function ActionInput() {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const active_mode = usePlayStore((s) => s.active_mode);
  const is_narrating = usePlayStore((s) => s.is_narrating);
  const { start: submitTurn, stop: stopGeneration } = useTurnStream();
  const playthrough = usePlayStore((s) => s.playthrough);

  const is_spectator = playthrough?.is_spectator ?? false;
  const is_not_my_turn = !is_spectator && playthrough?.can_act === false;

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [text]);

  const handleSubmit = () => {
    if (!text.trim() || is_narrating || is_spectator || is_not_my_turn) return;
    submitTurn(text.trim());
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  if (is_spectator) {
    return (
      <div className="absolute bottom-4 left-0 right-0 z-30 px-4 pointer-events-none flex justify-center">
        <div className="w-full max-w-2xl p-3 bg-stone-900/90 border border-stone-800/80 rounded-xl backdrop-blur-md text-center font-mono text-xs text-stone-400 flex items-center justify-center gap-2 pointer-events-auto">
          <svg
            className="w-4 h-4 text-stone-400 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.75}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
            />
          </svg>
          <span>You are spectating this session (Read-Only)</span>
        </div>
      </div>
    );
  }

  if (is_not_my_turn) {
    return (
      <div className="absolute bottom-4 left-0 right-0 z-30 px-4 pointer-events-none flex justify-center">
        <div className="w-full max-w-2xl p-3 bg-stone-900/90 border border-amber-900/40 rounded-xl backdrop-blur-md text-center font-mono text-xs text-amber-300 flex items-center justify-center gap-2 pointer-events-auto">
          <svg
            className="w-4 h-4 text-amber-400 shrink-0 animate-pulse"
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
          <span>Waiting for the other player's turn...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="absolute bottom-4 left-0 right-0 z-30 px-4 pointer-events-none flex justify-center">
      <div className="w-full max-w-3xl p-3 bg-stone-950/90 border border-amber-900/30 rounded-xl backdrop-blur-xl shadow-xl flex flex-col gap-2 pointer-events-auto">
        <ActionModePills />

        <div className="relative flex items-end gap-2">
          <textarea
            ref={textareaRef}
            rows={1}
            value={text}
            disabled={is_narrating}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={PLACEHOLDERS[active_mode] || PLACEHOLDERS.do}
            className="flex-1 bg-stone-900/60 text-stone-100 placeholder-stone-500 font-serif text-[15px] p-3 rounded-lg border border-stone-800/40 focus:border-amber-500/50 focus:outline-none focus:ring-1 focus:ring-amber-500/30 resize-none transition-all leading-relaxed"
          />

          {is_narrating ? (
            <button
              type="button"
              onClick={stopGeneration}
              className="px-4 py-3 bg-stone-900 hover:bg-stone-800 border border-red-900/50 text-red-400 rounded-lg font-mono text-xs flex items-center gap-1.5 transition-all cursor-pointer"
              title="Stop narration streaming"
            >
              <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
                <rect x="6" y="6" width="12" height="12" rx="1.5" />
              </svg>
              <span>Stop</span>
            </button>
          ) : (
            <button
              type="button"
              disabled={!text.trim()}
              onClick={handleSubmit}
              className={`px-4 py-3 rounded-lg font-mono text-xs flex items-center gap-1.5 transition-all ${
                text.trim()
                  ? "bg-amber-500 hover:bg-amber-400 text-stone-950 font-semibold cursor-pointer"
                  : "bg-stone-900 text-stone-600 cursor-not-allowed border border-stone-800/30"
              }`}
              title="Submit action (Cmd/Ctrl + Enter)"
            >
              <span>Submit</span>
              <svg
                className="w-3.5 h-3.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M14 5l7 7m0 0l-7 7m7-7H3"
                />
              </svg>
            </button>
          )}
        </div>

        <div className="flex items-center justify-between text-[11px] font-mono text-stone-500 px-1 pt-0.5">
          <span className="uppercase tracking-wider">
            Mode:{" "}
            <strong className="text-stone-300 font-semibold">
              {active_mode}
            </strong>
          </span>
          <span>
            Press{" "}
            <kbd className="px-1.5 py-0.5 rounded bg-stone-900 border border-stone-800 text-stone-400">
              Ctrl/Cmd + Enter
            </kbd>{" "}
            to submit
          </span>
        </div>
      </div>
    </div>
  );
}
