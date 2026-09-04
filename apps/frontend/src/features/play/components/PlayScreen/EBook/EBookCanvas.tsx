import { useEffect, useRef, useState } from "react";
import { usePlayStore } from "../../../stores/play.store";
import { EntityHighlightItem } from "../../../types/play.types";
import { EBookPrologueCard } from "./EBookPrologueCard";
import { EBookTurnEntry } from "./EBookTurnEntry";
import { EntityInspectTooltip } from "./EntityInspectTooltip";
import { useEntityHighlighter } from "./useEntityHighlighter";

export function EBookCanvas() {
  const playthrough = usePlayStore((s) => s.playthrough);
  const isNarrating = usePlayStore((s) => s.is_narrating);
  const streamingText = usePlayStore((s) => s.streaming_text);
  const lastAction = usePlayStore((s) => s.last_submitted_action);
  const activeMode = usePlayStore((s) => s.active_mode);
  const openActionDrawer = usePlayStore((s) => s.openActionDrawer);
  const stopGeneration = usePlayStore((s) => s.stopGeneration);

  const containerRef = useRef<HTMLDivElement>(null);
  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const [selectedEntity, setSelectedEntity] =
    useState<EntityHighlightItem | null>(null);
  const [entityAnchorRect, setEntityAnchorRect] = useState<DOMRect | null>(
    null,
  );

  const knownEntities = useEntityHighlighter(
    playthrough?.story_cards,
    playthrough?.key_facts,
    playthrough?.entities,
  );

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
    setShowScrollBottom(scrollHeight - scrollTop - clientHeight > 120);
  };

  useEffect(() => {
    if (isNarrating || playthrough?.turns.length) {
      scrollToBottom();
    }
  }, [isNarrating, streamingText, playthrough?.turns.length]);

  if (!playthrough) return null;

  const handleSelectEntity = (entity: EntityHighlightItem, rect: DOMRect) => {
    setSelectedEntity(entity);
    setEntityAnchorRect(rect);
  };

  const isSilentContinue = lastAction === "Continue the story.";

  return (
    <main
      ref={containerRef}
      onScroll={handleScroll}
      className="relative flex-1 w-full h-full overflow-y-auto px-4 sm:px-8 md:px-12 pt-6 pb-36 scrollbar-minimal selection:bg-zinc-800 selection:text-white"
    >
      <div className="max-w-3xl w-full mx-auto min-h-full flex flex-col">
        {/* Turn 0: Frontispiece / Prologue Card */}
        <EBookPrologueCard
          premise={playthrough.opening_premise}
          characterName={playthrough.character_name}
          onStartAction={openActionDrawer}
        />

        {/* Turned Chapters Feed */}
        {playthrough.turns.map((turn, index) => (
          <EBookTurnEntry
            key={turn.id}
            turn={turn}
            turnIndex={index}
            isLatest={index === playthrough.turns.length - 1}
            knownEntities={knownEntities}
            onSelectEntity={handleSelectEntity}
          />
        ))}

        {/* Live Streaming Chapter */}
        {isNarrating && (
          <section className="my-8 pt-6 border-t border-inherit/20 animate-fade-in">
            <header className="flex items-center justify-between font-mono text-xs opacity-60 mb-4 tracking-wider">
              <span className="uppercase flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-zinc-300 animate-ping" />
                Inscribing Chapter {playthrough.turns.length + 1}...
              </span>
              <button
                type="button"
                onClick={stopGeneration}
                className="px-2.5 py-1 rounded border border-zinc-700 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 cursor-pointer font-mono text-[10px]"
              >
                Stop
              </button>
            </header>

            {!isSilentContinue && lastAction && (
              <aside className="mb-5 pl-4 border-l-2 border-zinc-700 italic font-serif text-sm opacity-80">
                <span className="font-mono text-xs not-italic opacity-70 mr-1.5 uppercase font-medium">
                  {playthrough.character_name} ({activeMode}):
                </span>
                "{lastAction}"
              </aside>
            )}

            <div className="font-serif text-base md:text-lg leading-relaxed space-y-4">
              {streamingText ? (
                <p>
                  {streamingText}
                  <span className="inline-block w-2 h-4 ml-1 bg-zinc-300 animate-pulse align-middle" />
                </p>
              ) : (
                <p className="italic opacity-50 text-sm">
                  The narrator considers your choices...
                </p>
              )}
            </div>
          </section>
        )}
      </div>

      {/* Floating Bookmark: Jump to Latest */}
      {showScrollBottom && (
        <button
          type="button"
          onClick={scrollToBottom}
          className="fixed bottom-24 right-6 py-2 px-3 rounded-full bg-zinc-900 border border-zinc-700 text-zinc-200 font-mono text-xs font-medium shadow-lg hover:bg-zinc-800 transition-all cursor-pointer z-30 flex items-center gap-1.5"
        >
          <span>Latest Chapter</span>
          <span>↓</span>
        </button>
      )}

      {/* Entity Inspection Tooltip Popover */}
      <EntityInspectTooltip
        entity={selectedEntity}
        anchorRect={entityAnchorRect}
        onClose={() => setSelectedEntity(null)}
      />
    </main>
  );
}
