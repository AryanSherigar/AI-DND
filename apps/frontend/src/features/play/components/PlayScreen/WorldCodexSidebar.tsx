import { useState } from "react";
import { usePlayStore } from "../../stores/play.store";

interface WorldCodexSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
}

export function WorldCodexSidebar({
  isOpen,
  onToggle,
}: WorldCodexSidebarProps) {
  const playthrough = usePlayStore((s) => s.playthrough);
  const [activeTab, setActiveTab] = useState<"lore" | "facts" | "cards">(
    "lore",
  );

  if (!playthrough) return null;

  return (
    <aside
      className={`fixed lg:relative top-0 left-0 h-full z-40 bg-stone-950/95 border-r border-stone-900 backdrop-blur-md transition-all duration-300 flex flex-col shrink-0 ${
        isOpen
          ? "w-80 opacity-100 translate-x-0"
          : "w-0 opacity-0 -translate-x-full lg:translate-x-0 pointer-events-none"
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-stone-900">
        <div className="flex items-center gap-2.5">
          <svg
            className="w-5 h-5 text-stone-400"
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
          <h2 className="font-mono text-xs tracking-wider uppercase text-stone-400 font-medium">
            World Codex
          </h2>
        </div>
        <button
          onClick={onToggle}
          className="p-1 rounded text-stone-400 hover:text-stone-200 hover:bg-stone-900 transition-colors"
          title="Collapse Codex"
        >
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
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-stone-900 font-mono text-xs">
        <button
          onClick={() => setActiveTab("lore")}
          className={`flex-1 py-3 text-center transition-colors border-b-2 ${
            activeTab === "lore"
              ? "border-amber-500 text-stone-100 font-medium"
              : "border-transparent text-stone-400 hover:text-stone-200"
          }`}
        >
          Lore
        </button>
        <button
          onClick={() => setActiveTab("facts")}
          className={`flex-1 py-3 text-center transition-colors border-b-2 ${
            activeTab === "facts"
              ? "border-amber-500 text-stone-100 font-medium"
              : "border-transparent text-stone-400 hover:text-stone-200"
          }`}
        >
          Facts{" "}
          <span className="text-stone-500 text-[11px] font-normal ml-0.5">
            {playthrough.key_facts.length}
          </span>
        </button>
        <button
          onClick={() => setActiveTab("cards")}
          className={`flex-1 py-3 text-center transition-colors border-b-2 ${
            activeTab === "cards"
              ? "border-amber-500 text-stone-100 font-medium"
              : "border-transparent text-stone-400 hover:text-stone-200"
          }`}
        >
          Cards{" "}
          <span className="text-stone-500 text-[11px] font-normal ml-0.5">
            {playthrough.story_cards.length}
          </span>
        </button>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-stone-300 text-sm scrollbar-minimal">
        {activeTab === "lore" && (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <h3 className="font-mono text-[11px] uppercase text-stone-400 tracking-wider font-medium">
                Scenario Premise
              </h3>
              <p className="font-serif leading-relaxed text-stone-200 bg-stone-900/50 p-3.5 rounded-lg text-sm">
                {playthrough.opening_premise}
              </p>
            </div>
            <div className="space-y-1.5">
              <h3 className="font-mono text-[11px] uppercase text-stone-400 tracking-wider font-medium">
                World History & Lore
              </h3>
              <p className="font-serif leading-relaxed text-stone-300/90 bg-stone-900/50 p-3.5 rounded-lg text-sm">
                {playthrough.world_lore}
              </p>
            </div>
          </div>
        )}

        {activeTab === "facts" && (
          <div className="space-y-2">
            {playthrough.key_facts.map((fact, i) => (
              <div
                key={i}
                className="flex items-start gap-2.5 p-3 rounded-lg bg-stone-900/50 text-sm font-serif text-stone-300 leading-relaxed"
              >
                <span className="font-mono text-stone-500 text-xs mt-0.5">
                  •
                </span>
                <span>{fact}</span>
              </div>
            ))}
          </div>
        )}

        {activeTab === "cards" && (
          <div className="space-y-3">
            {playthrough.story_cards.map((card) => (
              <div
                key={card.id}
                className="p-3.5 rounded-lg bg-stone-900/60 hover:bg-stone-900/80 transition-colors"
              >
                <div className="flex items-center justify-between mb-1.5">
                  <h4 className="font-serif text-stone-200 font-semibold text-sm">
                    {card.title}
                  </h4>
                  <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-stone-800/60 text-stone-400 uppercase tracking-wider">
                    {card.category}
                  </span>
                </div>
                <p className="font-serif text-xs text-stone-400 leading-relaxed">
                  {card.content}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
