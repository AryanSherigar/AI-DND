import { useEffect, useRef, useState } from "react";
import { usePlayStore } from "../../../stores/play.store";
import { TurnEntry } from "./TurnEntry";
import { NarrationStream } from "../NarrationStream";

export function TurnHistory() {
  const playthrough = usePlayStore((s) => s.playthrough);
  const is_narrating = usePlayStore((s) => s.is_narrating);
  const streaming_text = usePlayStore((s) => s.streaming_text);

  const containerRef = useRef<HTMLDivElement>(null);
  const [showScrollBottom, setShowScrollBottom] = useState(false);

  const scrollToBottom = () => {
    if (containerRef.current) {
      containerRef.current.scrollTo({
        top: containerRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  };

  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 100;
    setShowScrollBottom(!isAtBottom);
  };

  useEffect(() => {
    if (is_narrating || playthrough?.turns.length) {
      scrollToBottom();
    }
  }, [is_narrating, streaming_text, playthrough?.turns.length]);

  if (!playthrough) return null;

  return (
    <div className="relative flex-1 flex flex-col h-full min-h-0 overflow-hidden">
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 md:px-8 pt-6 pb-36 space-y-6 scrollbar-minimal"
      >
        {/* Opening Premise Callout Box (Keeps Border) */}
        <div className="p-5 rounded-xl bg-stone-900/40 border border-amber-900/40 space-y-2.5">
          <div className="flex items-center gap-2 font-mono text-[11px] text-stone-400 uppercase tracking-wider font-medium">
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
            <span>Opening Premise</span>
          </div>
          <p className="font-serif text-stone-200 text-[15px] leading-relaxed italic">
            "{playthrough.opening_premise}"
          </p>
        </div>

        {/* Turn Log List */}
        <div className="divide-y divide-stone-900/60">
          {playthrough.turns.map((turn, index) => (
            <TurnEntry
              key={turn.id}
              turn={turn}
              isLatest={index === playthrough.turns.length - 1}
            />
          ))}
        </div>

        {/* Live Token Streaming Block */}
        <NarrationStream />
      </div>

      {/* Floating Scroll to Bottom Button */}
      {showScrollBottom && (
        <button
          type="button"
          onClick={scrollToBottom}
          className="absolute bottom-36 right-6 py-1.5 px-3 rounded-full bg-amber-500 text-stone-950 font-mono text-xs font-semibold shadow-md flex items-center gap-1.5 hover:bg-amber-400 transition-all cursor-pointer z-40"
        >
          <span>Scroll to latest</span>
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
              d="M19 14l-7 7m0 0l-7-7m7 7V3"
            />
          </svg>
        </button>
      )}
    </div>
  );
}
