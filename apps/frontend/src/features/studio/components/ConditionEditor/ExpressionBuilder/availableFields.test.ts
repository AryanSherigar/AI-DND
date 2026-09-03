import { describe, expect, it } from "vitest";
import { StateFieldDefinition } from "../../../types/scenario.types";
import { EntityResponse } from "../../../types/entity.types";
import { buildAvailableFields } from "./availableFields";

describe("buildAvailableFields", () => {
  it("walks nested object fields into dot-paths and includes entity attributes", () => {
    const stateSchema: Record<string, StateFieldDefinition> = {
      player: {
        type: "object",
        fields: {
          health: { type: "number", label: "Health" },
          inventory: { type: "list", item_type: "string" },
        },
      },
      warden_awareness: {
        type: "derived",
        label: "Warden Awareness",
        formula: "the_warden.awareness",
      },
      is_night: { type: "boolean" },
    };

    const entities: EntityResponse[] = [
      {
        entity_id: "1",
        scenario_id: "s1",
        entity_type: "character",
        canonical_name: "The Warden",
        aliases: [],
        description: null,
        obtainable: null,
        attributes_schema: {
          health: { type: "number", label: "Health" },
          vulnerable: { type: "boolean" },
        },
        narrator_instruction: null,
      },
    ];

    const result = buildAvailableFields(stateSchema, entities);

    expect(result).toEqual([
      { path: "player.health", label: "Health", type: "number" },
      { path: "warden_awareness", label: "Warden Awareness", type: "string" },
      { path: "is_night", label: "is_night", type: "boolean" },
      { path: "the_warden.health", label: "Health", type: "number" },
      { path: "the_warden.vulnerable", label: "vulnerable", type: "boolean" },
    ]);
  });

  it("returns an empty array for empty schema and no entities", () => {
    expect(buildAvailableFields({}, [])).toEqual([]);
  });
});
