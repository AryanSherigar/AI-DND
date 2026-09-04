import { useMemo } from "react";
import {
  StoryCard,
  EntityHighlightItem,
  MasterEntity,
} from "../../../types/play.types";

function buildMasterEntityHighlights(
  masterEntities: MasterEntity[],
): EntityHighlightItem[] {
  return masterEntities.flatMap((entity) => {
    const attributes = Object.entries(entity.attributes_schema).map(
      ([key, schema]) => ({
        label: schema.label ?? key,
        value: String(entity.attributes[key] ?? "—"),
      }),
    );
    const names = [entity.canonical_name, ...entity.aliases];
    return names.map((name) => ({
      id: entity.entity_id,
      name,
      category: entity.entity_type,
      summary: entity.description ?? "",
      attributes,
    }));
  });
}

export function useEntityHighlighter(
  storyCards: StoryCard[] = [],
  keyFacts: string[] = [],
  masterEntities: MasterEntity[] = [],
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

    const masterEntityHighlights = buildMasterEntityHighlights(masterEntities);

    return [...cardEntities, ...factEntities, ...masterEntityHighlights];
  }, [storyCards, keyFacts, masterEntities]);
}
