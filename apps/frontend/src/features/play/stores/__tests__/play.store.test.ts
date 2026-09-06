import { describe, it, expect, vi, beforeEach } from "vitest";
import { usePlayStore } from "../play.store";
import { PlaythroughData } from "../../types/play.types";
import { SSEHandlers } from "@/shared/lib/sse-client";
import { MinigameEventPayload } from "@/shared/types/minigame.types";

let capturedHandlers: SSEHandlers | null = null;
let capturedBody: unknown = null;

vi.mock("@/shared/lib/sse-client", () => ({
  createPostSSEConnection: (
    _url: string,
    body: unknown,
    _token: string | null,
    handlers: SSEHandlers,
  ) => {
    capturedHandlers = handlers;
    capturedBody = body;
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
    pending_minigame: null,
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
          {
            path: "player.health",
            label: "Health",
            before: 100,
            after: 85,
            delta: -15,
          },
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

describe("play.store — minigame trigger/result handling", () => {
  beforeEach(() => {
    capturedHandlers = null;
    capturedBody = null;
    usePlayStore.setState({
      playthrough: buildPlaythrough(),
      pending_minigame_trigger: null,
      active_minigame: null,
      streaming_text: "",
      is_narrating: false,
    });
  });

  const minigamePayload: MinigameEventPayload = {
    minigame_id: "mg-1",
    minigame_type: "replit_embed",
    label: "Rune Puzzle",
    dodge_config: null,
    replit_embed_url: "https://example.replit.dev",
    timeout_seconds: 20,
  };

  it("buffers a minigame event and only promotes it to active_minigame on done", () => {
    usePlayStore.getState().submitTurn("I open the door.");
    expect(capturedHandlers).not.toBeNull();

    capturedHandlers!.onEvent("minigame", JSON.stringify(minigamePayload));

    // Buffered only — the overlay must not appear mid-stream.
    expect(usePlayStore.getState().active_minigame).toBeNull();
    expect(usePlayStore.getState().pending_minigame_trigger).toEqual(
      minigamePayload,
    );

    capturedHandlers!.onEvent("done", "");

    expect(usePlayStore.getState().active_minigame).toEqual(minigamePayload);
    expect(usePlayStore.getState().pending_minigame_trigger).toBeNull();
  });

  it("submitMinigameResult posts action_kind minigame_result with the given payload", () => {
    usePlayStore.getState().submitMinigameResult({
      minigame_id: "mg-1",
      outcome_tag: "win",
      score: 10,
    });

    expect(capturedHandlers).not.toBeNull();
    expect(capturedBody).toMatchObject({
      action_kind: "minigame_result",
      minigame_result: { minigame_id: "mg-1", outcome_tag: "win", score: 10 },
    });
  });

  it("clearActiveMinigame nulls active_minigame immediately", () => {
    usePlayStore.setState({ active_minigame: minigamePayload });
    usePlayStore.getState().clearActiveMinigame();
    expect(usePlayStore.getState().active_minigame).toBeNull();
  });

  it("updates and clears reader_font_override", () => {
    usePlayStore.getState().setReaderFontOverride("special-elite");
    expect(usePlayStore.getState().reader_font_override).toBe("special-elite");

    usePlayStore.getState().setReaderFontOverride(null);
    expect(usePlayStore.getState().reader_font_override).toBeNull();
  });
});
