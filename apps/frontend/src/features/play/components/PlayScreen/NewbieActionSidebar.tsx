import { usePlayStore } from "../../stores/play.store";
import { ActionInput } from "./ActionInput";
import { StoryCardsPanel } from "./StoryCardsPanel";

interface NewbieActionSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
}

export function NewbieActionSidebar({
  isOpen,
  onToggle,
}: NewbieActionSidebarProps) {
  const playthrough = usePlayStore((s) => s.playthrough);

  if (!playthrough) return null;

  return (
    <aside
      className={`fixed lg:relative top-0 right-0 h-full z-40 bg-stone-950/95 border-l border-stone-900 backdrop-blur-md transition-all duration-300 flex flex-col shrink-0 overflow-hidden ${
        isOpen
          ? "w-80 opacity-100 translate-x-0"
          : "w-0 opacity-0 translate-x-full lg:translate-x-0 pointer-events-none"
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-stone-900">
        <button
          onClick={onToggle}
          className="p-1 rounded text-stone-400 hover:text-stone-200 hover:bg-stone-900 transition-colors"
          title="Collapse Panel"
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
              d="M9 5l7 7-7 7"
            />
          </svg>
        </button>
        <h2 className="font-mono text-xs tracking-wider uppercase text-stone-400 font-medium">
          Story Cards
        </h2>
      </div>

      {/* Story Cards (scrollable) + floating Action Input, anchored to this panel */}
      <div className="relative flex-1 min-h-0">
        <div className="h-full overflow-y-auto p-4 pb-36 scrollbar-minimal">
          <StoryCardsPanel storyCards={playthrough.story_cards} />
        </div>
        <ActionInput />
      </div>
    </aside>
  );
}
