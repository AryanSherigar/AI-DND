import { useState, useEffect } from "react";
import { usePlayStore } from "../../../stores/play.store";

interface EBookCodexDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export function EBookCodexDrawer({ isOpen, onClose }: EBookCodexDrawerProps) {
  const playthrough = usePlayStore((s) => s.playthrough);
  const theme = usePlayStore((s) => s.ebook_theme);
  const isSepia = theme === "antique-sepia";
  const [activeTab, setActiveTab] = useState<"lore" | "facts" | "cards">(
    "lore",
  );

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!playthrough) return null;

  const drawerStyle = isSepia
    ? "bg-[#faf4e8] border-[#d8c7a8] text-[#2c2217]"
    : "bg-[#09090b] border-zinc-800 text-zinc-100";

  const cardStyle = isSepia
    ? "bg-[#f5ebd7] border-[#e2d5be]"
    : "bg-zinc-900/70 border-zinc-800/80";

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 bg-black/70 z-40 backdrop-blur-xs transition-opacity"
        />
      )}

      {/* Slide-out Drawer */}
      <aside
        className={`fixed top-0 left-0 h-full w-80 sm:w-96 z-50 border-r shadow-2xl transition-transform duration-300 flex flex-col ${drawerStyle} ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-inherit/20">
          <div className="flex items-center gap-2">
            <span className="text-base">📖</span>
            <h2 className="font-mono text-xs tracking-wider uppercase font-semibold">
              World Codex
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded opacity-60 hover:opacity-100 transition-opacity font-mono text-xs cursor-pointer"
            title="Close Codex (Esc)"
          >
            ✕ Close
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-inherit/20 font-mono text-xs">
          <button
            type="button"
            onClick={() => setActiveTab("lore")}
            className={`flex-1 py-3 text-center transition-colors border-b-2 cursor-pointer ${
              activeTab === "lore"
                ? isSepia
                  ? "border-[#2c2217] font-bold"
                  : "border-zinc-200 font-bold"
                : "border-transparent opacity-60 hover:opacity-100"
            }`}
          >
            Lore
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("facts")}
            className={`flex-1 py-3 text-center transition-colors border-b-2 cursor-pointer ${
              activeTab === "facts"
                ? isSepia
                  ? "border-[#2c2217] font-bold"
                  : "border-zinc-200 font-bold"
                : "border-transparent opacity-60 hover:opacity-100"
            }`}
          >
            Facts ({playthrough.key_facts.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("cards")}
            className={`flex-1 py-3 text-center transition-colors border-b-2 cursor-pointer ${
              activeTab === "cards"
                ? isSepia
                  ? "border-[#2c2217] font-bold"
                  : "border-zinc-200 font-bold"
                : "border-transparent opacity-60 hover:opacity-100"
            }`}
          >
            Cards ({playthrough.story_cards.length})
          </button>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-minimal">
          {activeTab === "lore" && (
            <div className="space-y-4">
              <div className="space-y-1.5">
                <h3 className="font-mono text-[11px] uppercase tracking-wider opacity-60 font-medium">
                  Scenario Premise
                </h3>
                <p
                  className={`font-serif leading-relaxed p-3.5 rounded-xl border text-sm italic ${cardStyle}`}
                >
                  "{playthrough.opening_premise}"
                </p>
              </div>
              <div className="space-y-1.5">
                <h3 className="font-mono text-[11px] uppercase tracking-wider opacity-60 font-medium">
                  World History & Lore
                </h3>
                <p
                  className={`font-serif leading-relaxed p-3.5 rounded-xl border text-sm ${cardStyle}`}
                >
                  {playthrough.world_lore}
                </p>
              </div>
            </div>
          )}

          {activeTab === "facts" && (
            <div className="space-y-2.5">
              {playthrough.key_facts.map((fact: string, i: number) => (
                <div
                  key={i}
                  className={`p-3 rounded-xl border text-sm font-serif leading-relaxed flex items-start gap-2.5 ${cardStyle}`}
                >
                  <span className="text-zinc-500 font-mono text-xs mt-0.5">
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
                  className={`p-3.5 rounded-xl border space-y-1.5 ${cardStyle}`}
                >
                  <div className="flex items-center justify-between">
                    <h4 className="font-serif font-bold text-sm">
                      {card.title}
                    </h4>
                    <span
                      className={`font-mono text-[10px] px-2 py-0.5 rounded uppercase tracking-wider font-medium ${
                        isSepia
                          ? "bg-[#e2d5be]/50 text-[#2c2217]"
                          : "bg-zinc-800 text-zinc-300 border border-zinc-700/60"
                      }`}
                    >
                      {card.category}
                    </span>
                  </div>
                  <p className="font-serif text-xs opacity-80 leading-relaxed">
                    {card.content}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
