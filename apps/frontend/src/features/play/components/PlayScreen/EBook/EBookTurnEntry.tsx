import { ReactNode } from "react";
import { usePlayStore } from "../../../stores/play.store";
import { EntityHighlightItem } from "../../../types/play.types";
import { ChapterSummaryStrip } from "./ChapterSummaryStrip";
import { DiceRollCard } from "./DiceRollCard";
import { EBookTurnEntryProps } from "./ebook.types";

interface ParagraphProps {
  paragraph: string;
  isFirst: boolean;
  knownEntities: EntityHighlightItem[];
  onSelectEntity: (entity: EntityHighlightItem, rect: DOMRect) => void;
}

function HighlightedParagraph({
  paragraph,
  isFirst,
  knownEntities,
  onSelectEntity,
}: ParagraphProps) {
  const parts = renderHighlightedText(paragraph, knownEntities, onSelectEntity);
  const dropCapClass = isFirst
    ? "first-letter:text-3xl md:first-letter:text-4xl first-letter:font-serif first-letter:font-bold first-letter:float-left first-letter:mr-2.5 first-letter:leading-none first-letter:text-inherit"
    : "";

  return (
    <p
      className={`font-serif text-base md:text-lg leading-relaxed mb-4 ${dropCapClass}`}
    >
      {parts}
    </p>
  );
}

function renderHighlightedText(
  text: string,
  entities: EntityHighlightItem[],
  onSelect: (entity: EntityHighlightItem, rect: DOMRect) => void,
): ReactNode[] {
  if (!entities.length) return [text];

  const sorted = [...entities].sort((a, b) => b.name.length - a.name.length);
  const regex = new RegExp(
    `\\b(${sorted.map((e) => escapeRegExp(e.name)).join("|")})\\b`,
    "gi",
  );

  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.substring(lastIndex, match.index));
    }
    const matchedText = match[0];
    const foundEntity = sorted.find(
      (e) => e.name.toLowerCase() === matchedText.toLowerCase(),
    );

    if (foundEntity) {
      nodes.push(
        <button
          key={`${match.index}-${matchedText}`}
          type="button"
          onClick={(e) =>
            onSelect(foundEntity, e.currentTarget.getBoundingClientRect())
          }
          className="underline decoration-zinc-500/50 decoration-dashed underline-offset-4 hover:bg-zinc-800/40 hover:text-white px-0.5 rounded transition-colors text-inherit font-inherit cursor-pointer inline"
          title={`Inspect ${foundEntity.name}`}
        >
          {matchedText}
        </button>,
      );
    } else {
      nodes.push(matchedText);
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    nodes.push(text.substring(lastIndex));
  }
  return nodes;
}

function escapeRegExp(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function EBookTurnEntry({
  turn,
  turnIndex,
  isLatest: _isLatest,
  knownEntities,
  onSelectEntity,
}: EBookTurnEntryProps) {
  const isSilentContinue = turn.action_text === "Continue the story.";
  const characterName = usePlayStore(
    (s) => s.playthrough?.character_name ?? "Adventurer",
  );
  const paragraphs = turn.narration_text.split(/\n\s*\n/).filter(Boolean);

  return (
    <section className="my-8 pt-6 border-t border-inherit/20 first:border-t-0">
      <header className="flex items-center justify-between font-mono text-xs opacity-60 mb-4 tracking-wider">
        <span className="uppercase">Chapter {turnIndex + 1}</span>
        <span>
          {new Date(turn.created_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </header>

      {!isSilentContinue && (
        <aside className="mb-5 pl-4 border-l-2 border-zinc-700 italic font-serif text-sm opacity-80">
          <span className="font-mono text-xs not-italic opacity-70 mr-1.5 uppercase font-medium">
            {characterName} ({turn.action_mode}):
          </span>
          "{turn.action_text}"
        </aside>
      )}

      <article className="prose-book">
        {paragraphs.map((para: string, idx: number) => (
          <HighlightedParagraph
            key={idx}
            paragraph={para}
            isFirst={idx === 0}
            knownEntities={knownEntities}
            onSelectEntity={onSelectEntity}
          />
        ))}
      </article>

      {turn.chapter_delta && (
        <>
          {turn.chapter_delta.dice_rolls.map((roll, idx) => (
            <DiceRollCard key={idx} roll={roll} />
          ))}
          <ChapterSummaryStrip delta={turn.chapter_delta} />
        </>
      )}
    </section>
  );
}
