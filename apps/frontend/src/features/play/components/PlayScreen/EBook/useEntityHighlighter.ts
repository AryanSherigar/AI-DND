import { useMemo } from "react";
import { StoryCard, EntityHighlightItem } from "../../../types/play.types";

export function useEntityHighlighter(
  storyCards: StoryCard[] = [],
  keyFacts: string[] = [],
): EntityHighlightItem[] {
  return useMemo(() => {
    const cardEntities: EntityHighlightItem[] = storyCards.map((card) => ({
      id: card.id,
      name: card.title,
      category: card.category || "lore",
      summary: card.content,
    }));

    const factEntities: EntityHighlightItem[] = keyFacts
      .filter((fact) => fact.includes(":") || fact.length > 5)
      .slice(0, 5)
      .map((fact, index) => {
        const title = fact.includes(":")
          ? fact.split(":")[0].trim()
          : `Fact ${index + 1}`;
        return {
          id: `fact-${index}`,
          name: title,
          category: "fact",
          summary: fact,
        };
      });

    return [...cardEntities, ...factEntities];
  }, [storyCards, keyFacts]);
}
