import { describe, it, expect, vi, beforeEach } from "vitest";
import { usePlayStore } from "../play.store";
import { PlaythroughData } from "../../types/play.types";
import { SSEHandlers } from "@/shared/lib/sse-client";

let capturedHandlers: SSEHandlers | null = null;

vi.mock("@/shared/lib/sse-client", () => ({
  createPostSSEConnection: (
    _url: string,
    _body: unknown,
    _token: string | null,
    handlers: SSEHandlers,
  ) => {
    capturedHandlers = handlers;
    return vi.fn();
  },
}));

function buildPlaythrough(): PlaythroughData {
  return {
    playthrough_id: "pt-1",
    scenario_id: "sc-1",
    scenario_title: "The Hollow Cairn",
    mode: "master",
    creator_name: "Creator",
    opening_premise: "Begin.",
    world_lore: "",
    key_facts: [],
    story_cards: [],
    character_name: "Adventurer",
    custom_fields: [],
    turns: [],
    is_spectator: false,
    participant_id: "participant-1",
    can_act: true,
    next_actor_label: null,
    entities: [],
    active_conditions: [],
    objectives: [],
    player_stats: [],
    player_inventory: [],
  };
}

describe("play.store — turn_summary handling", () => {
  beforeEach(() => {
    capturedHandlers = null;
    usePlayStore.setState({
      playthrough: buildPlaythrough(),
      pending_chapter_delta: null,
      streaming_text: "",
      is_narrating: false,
    });
  });

  it("holds the delta on turn_summary and only attaches it to the committed turn on done", () => {
    usePlayStore.getState().submitTurn("I strike the warden.");
    expect(capturedHandlers).not.toBeNull();

    capturedHandlers!.onEvent(
      "narration",
      "The blade connects with a dull thud.",
    );
    // Not yet committed — the summary strip must not appear mid-stream.
    expect(usePlayStore.getState().playthrough?.turns).toHaveLength(0);

    capturedHandlers!.onEvent(
      "turn_summary",
      JSON.stringify({
        stat_changes: [
          { path: "player.health", label: "Health", before: 100, after: 85, delta: -15 },
        ],
        inventory_changes: [],
        dice_rolls: [],
        active_conditions: ["Bleeding Out"],
      }),
    );

    // active_conditions is live, applied immediately.
    expect(usePlayStore.getState().playthrough?.active_conditions).toEqual([
      "Bleeding Out",
    ]);
    // The delta is held, not yet on any committed turn.
    expect(usePlayStore.getState().pending_chapter_delta).not.toBeNull();
    expect(usePlayStore.getState().playthrough?.turns).toHaveLength(0);

    capturedHandlers!.onEvent("done", "");

    const turns = usePlayStore.getState().playthrough?.turns ?? [];
    expect(turns).toHaveLength(1);
    expect(turns[0].chapter_delta?.stat_changes[0].label).toBe("Health");
    expect(usePlayStore.getState().pending_chapter_delta).toBeNull();
  });
});
