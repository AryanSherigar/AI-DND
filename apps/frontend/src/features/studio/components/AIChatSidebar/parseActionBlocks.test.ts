import { describe, expect, it } from "vitest";
import { parseMessageSegments } from "./parseActionBlocks";

describe("parseMessageSegments", () => {
  it("parses plain text without action blocks", () => {
    const text = "Hello, how can I help you world-build today?";
    const segments = parseMessageSegments(text);
    expect(segments).toHaveLength(1);
    expect(segments[0]).toEqual({ type: "text", content: text });
  });

  it("parses a single action block for conflict", () => {
    const text =
      "Here is a conflict:\n```action:conflict\nThe dragon has awakened.\n```\nWhat do you think?";
    const segments = parseMessageSegments(text);
    expect(segments).toHaveLength(3);
    expect(segments[0]).toEqual({
      type: "text",
      content: "Here is a conflict:\n",
    });
    expect(segments[1]).toEqual({
      type: "action",
      block: {
        target: "conflict",
        metadata: undefined,
        content: "The dragon has awakened.",
      },
    });
    expect(segments[2]).toEqual({
      type: "text",
      content: "\nWhat do you think?",
    });
  });

  it("parses action block with JSON metadata for story_card", () => {
    const text =
      '```action:story_card {"type": "Faction", "name": "The Iron Order"}\nA martial guild dedicated to order.\n```';
    const segments = parseMessageSegments(text);
    expect(segments).toHaveLength(1);
    expect(segments[0]).toEqual({
      type: "action",
      block: {
        target: "story_card",
        metadata: { type: "Faction", name: "The Iron Order" },
        content: "A martial guild dedicated to order.",
      },
    });
  });
});
