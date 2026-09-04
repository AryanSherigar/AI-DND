import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { useEntityHighlighter } from "../EBook/useEntityHighlighter";
import { MasterEntity, StoryCard } from "../../../types/play.types";

describe("useEntityHighlighter", () => {
  it("extracts entities from story cards and key facts", () => {
    const mockCards: StoryCard[] = [
      {
        id: "c1",
        title: "Eldergrove",
        category: "location",
        content: "An enchanted forest.",
      },
      {
        id: "c2",
        title: "Silver Blade",
        category: "item",
        content: "A glowing sword.",
      },
    ];
    const mockFacts = [
      "The King is missing from the capital",
      "Magic is forbidden in the realm",
    ];

    const { result } = renderHook(() =>
      useEntityHighlighter(mockCards, mockFacts),
    );

    expect(result.current.length).toBe(4);
    expect(result.current[0].name).toBe("Eldergrove");
    expect(result.current[1].name).toBe("Silver Blade");
  });

  it("handles empty arrays gracefully", () => {
    const { result } = renderHook(() => useEntityHighlighter([], []));
    expect(result.current).toEqual([]);
  });

  it("builds one highlight per master entity plus one per alias, with live attributes", () => {
    const masterEntities: MasterEntity[] = [
      {
        entity_id: "warden-1",
        entity_type: "character",
        canonical_name: "The Warden",
        aliases: ["the guardian"],
        description: "A tireless sentinel.",
        attributes_schema: { awareness: { type: "number", label: "Awareness" } },
        obtainable: null,
        attributes: { awareness: 40 },
      },
    ];

    const { result } = renderHook(() =>
      useEntityHighlighter([], [], masterEntities),
    );

    expect(result.current).toHaveLength(2);
    expect(result.current.map((e) => e.name)).toEqual([
      "The Warden",
      "the guardian",
    ]);
    expect(result.current[0].id).toBe("warden-1");
    expect(result.current[0].category).toBe("character");
    expect(result.current[0].attributes).toEqual([
      { label: "Awareness", value: "40" },
    ]);
  });
});
