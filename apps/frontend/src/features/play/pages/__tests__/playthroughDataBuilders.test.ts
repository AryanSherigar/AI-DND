import { describe, it, expect } from "vitest";
import { buildMasterPlaythroughData } from "../playthroughDataBuilders";
import { PlaythroughResponse } from "../../api/playthroughs.api";
import { TurnLogListResponse } from "../../api/turns.api";

function buildServerPlaythrough(
  overrides: Partial<PlaythroughResponse> = {},
): PlaythroughResponse {
  return {
    playthrough_id: "pt-1",
    scenario_id: "sc-1",
    scenario_title: "The Hollow Cairn",
    created_by: "user-1",
    state: {
      player: { health: 85, sanity: 98, inventory: ["sword-1"] },
      entities: { "warden-1": { awareness: 40 } },
    },
    checkpoint: null,
    turn_count: 0,
    status: "active",
    scenario_version: 1,
    scenario_snapshot: {
      mode: "master",
      setup_schema: [],
      state_schema: {
        player: {
          type: "object",
          fields: {
            health: { type: "number", label: "Health" },
            sanity: { type: "number" },
            inventory: { type: "list", item_type: "entity_ref" },
          },
        },
      },
      entities: [
        {
          entity_id: "warden-1",
          entity_type: "character",
          canonical_name: "The Warden",
          aliases: [],
          description: null,
          attributes_schema: { awareness: { type: "number" } },
          obtainable: null,
        },
        {
          entity_id: "sword-1",
          entity_type: "item",
          canonical_name: "Rusty Sword",
          aliases: [],
          description: null,
          attributes_schema: {},
          obtainable: true,
        },
      ],
      end_conditions: [
        {
          outcome_tag: "win",
          outcome_title: "The Ashen Ending",
          outcome_text: "The Warden kneels.",
          is_secret: false,
        },
        {
          outcome_tag: "win",
          outcome_title: "The Vigil's Ending",
          outcome_text: "You relieve it.",
          is_secret: true,
        },
      ],
    },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    participant_id: "participant-1",
    participants: [
      {
        participant_id: "participant-1",
        user_id: "u1",
        role: "owner",
        turn_order_position: 1,
      },
    ],
    active_conditions: ["Bleeding Out"],
    ...overrides,
  };
}

const emptyTurns: TurnLogListResponse = { items: [], total_count: 0 };

describe("buildMasterPlaythroughData", () => {
  it("merges live entity attributes onto the pinned snapshot entities", () => {
    const data = buildMasterPlaythroughData(
      buildServerPlaythrough(),
      emptyTurns,
      false,
    );

    const warden = data.entities.find((e) => e.entity_id === "warden-1");
    expect(warden?.attributes).toEqual({ awareness: 40 });
  });

  it("builds player_stats from non-list/non-entity_ref state_schema.player fields", () => {
    const data = buildMasterPlaythroughData(
      buildServerPlaythrough(),
      emptyTurns,
      false,
    );

    expect(data.player_stats).toEqual([
      { key: "health", label: "Health", value: 85 },
      { key: "sanity", label: "Sanity", value: 98 },
    ]);
  });

  it("resolves player_inventory entity ids against the entities list", () => {
    const data = buildMasterPlaythroughData(
      buildServerPlaythrough(),
      emptyTurns,
      false,
    );

    expect(data.player_inventory).toHaveLength(1);
    expect(data.player_inventory[0].canonical_name).toBe("Rusty Sword");
  });

  it("filters secret end_conditions out of objectives", () => {
    const data = buildMasterPlaythroughData(
      buildServerPlaythrough(),
      emptyTurns,
      false,
    );

    expect(data.objectives).toEqual([
      {
        outcome_title: "The Ashen Ending",
        outcome_tag: "win",
        outcome_text: "The Warden kneels.",
      },
    ]);
  });

  it("carries active_conditions through from the server response", () => {
    const data = buildMasterPlaythroughData(
      buildServerPlaythrough(),
      emptyTurns,
      false,
    );

    expect(data.active_conditions).toEqual(["Bleeding Out"]);
  });
});
