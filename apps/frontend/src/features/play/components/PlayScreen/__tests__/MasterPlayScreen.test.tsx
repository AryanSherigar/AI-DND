import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { MasterPlayScreen } from "../MasterPlayScreen";
import { usePlayStore } from "../../../stores/play.store";
import { PlaythroughData } from "../../../types/play.types";

function buildPlaythrough(
  overrides: Partial<PlaythroughData> = {},
): PlaythroughData {
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
    ended_outcome_tag: null,
    ended_outcome_title: null,
    ended_outcome_text: null,
    action_chips: [],
    ...overrides,
  };
}

function renderScreen() {
  return render(
    <MemoryRouter>
      <MasterPlayScreen />
    </MemoryRouter>,
  );
}

describe("MasterPlayScreen", () => {
  beforeEach(() => {
    usePlayStore.setState({
      playthrough: buildPlaythrough(),
      is_left_sidebar_open: false,
      is_right_sidebar_open: false,
      is_action_drawer_open: false,
      is_chronicle_modal_open: false,
      is_narrating: false,
      degraded_message: null,
    });
  });

  it("hides the status badge row when active_conditions is empty", () => {
    renderScreen();
    expect(screen.queryByText("Bleeding Out")).not.toBeInTheDocument();
  });

  it("shows status badges when active_conditions is non-empty", () => {
    usePlayStore.setState({
      playthrough: buildPlaythrough({ active_conditions: ["Bleeding Out"] }),
    });
    renderScreen();
    expect(screen.getByText("Bleeding Out")).toBeInTheDocument();
  });

  it("shows a waiting message and blocks the action drawer when it isn't the player's turn", () => {
    usePlayStore.setState({
      playthrough: buildPlaythrough({
        can_act: false,
        next_actor_label: "Player 2",
      }),
    });
    renderScreen();

    expect(screen.getByText(/Waiting for Player 2/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Take Action/i }),
    ).not.toBeInTheDocument();
  });

  it("opens the character drawer from the bottom bar trigger", () => {
    renderScreen();

    const drawer = screen.getByText("Character").closest("aside");
    expect(drawer).toHaveClass("translate-x-full");

    fireEvent.click(screen.getByTitle("Open Character Sheet"));
    expect(drawer).toHaveClass("translate-x-0");
  });

  it("hides the ending banner and allows the action drawer while in progress", () => {
    renderScreen();

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Take Action/i }),
    ).toBeInTheDocument();
  });

  it("shows the ending banner and blocks the action drawer once the playthrough has ended", () => {
    usePlayStore.setState({
      playthrough: buildPlaythrough({
        ended_outcome_tag: "win",
        ended_outcome_title: "The Ashen Ending",
        ended_outcome_text: "The Warden kneels.",
      }),
    });
    renderScreen();

    expect(screen.getByRole("alert")).toHaveTextContent("The Ashen Ending");
    expect(screen.getByRole("alert")).toHaveTextContent("The Warden kneels.");
    expect(screen.getByText(/This chronicle has ended/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Take Action/i }),
    ).not.toBeInTheDocument();
  });
});
