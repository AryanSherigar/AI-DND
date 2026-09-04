import { StoryCard } from "../../types/play.types";

interface StoryCardsPanelProps {
  storyCards: StoryCard[];
}

export function StoryCardsPanel({ storyCards }: StoryCardsPanelProps) {
  return (
    <div className="space-y-3">
      {storyCards.map((card) => (
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
  );
}
