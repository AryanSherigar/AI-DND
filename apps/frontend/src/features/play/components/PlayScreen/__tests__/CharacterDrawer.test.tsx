import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CharacterDrawer } from "../EBook/CharacterDrawer";
import { MasterEntity, Objective, PlayerStat } from "../../../types/play.types";

const playerStats: PlayerStat[] = [{ key: "health", label: "Health", value: 85 }];

const factionEntity: MasterEntity = {
  entity_id: "faction-1",
  entity_type: "faction",
  canonical_name: "The Vigil",
  aliases: [],
  description: null,
  attributes_schema: { reputation: { type: "number", label: "Reputation" } },
  obtainable: null,
  attributes: { reputation: 12 },
};

const swordEntity: MasterEntity = {
  entity_id: "sword-1",
  entity_type: "item",
  canonical_name: "Rusty Sword",
  aliases: [],
  description: null,
  attributes_schema: {},
  obtainable: true,
  attributes: {},
};

const objectives: Objective[] = [
  { outcome_title: "The Ashen Ending", outcome_tag: "win", outcome_text: "The Warden kneels." },
  { outcome_title: "Consumed", outcome_tag: "lose", outcome_text: "The cairn takes you." },
];

describe("CharacterDrawer", () => {
  it("shows player stats on the Stats tab by default", () => {
    render(
      <CharacterDrawer
        isOpen={true}
        onClose={vi.fn()}
        playerStats={playerStats}
        playerInventory={[]}
        entities={[]}
        objectives={[]}
      />,
    );

    expect(screen.getByText("Health")).toBeInTheDocument();
    expect(screen.getByText("85")).toBeInTheDocument();
  });

  it("switches to the Inventory tab and shows inventory items", () => {
    render(
      <CharacterDrawer
        isOpen={true}
        onClose={vi.fn()}
        playerStats={[]}
        playerInventory={[swordEntity]}
        entities={[]}
        objectives={[]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Inventory" }));
    expect(screen.getByText("Rusty Sword")).toBeInTheDocument();
  });

  it("switches to the Factions tab and only shows faction/organization entities", () => {
    render(
      <CharacterDrawer
        isOpen={true}
        onClose={vi.fn()}
        playerStats={[]}
        playerInventory={[]}
        entities={[factionEntity, swordEntity]}
        objectives={[]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Factions" }));
    expect(screen.getByText("The Vigil")).toBeInTheDocument();
    expect(screen.queryByText("Rusty Sword")).not.toBeInTheDocument();
  });

  it("groups objectives by outcome_tag and never renders a secret one, since Objective has no is_secret field to leak", () => {
    render(
      <CharacterDrawer
        isOpen={true}
        onClose={vi.fn()}
        playerStats={[]}
        playerInventory={[]}
        entities={[]}
        objectives={objectives}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Objectives" }));
    expect(screen.getByText(/The Ashen Ending/i)).toBeInTheDocument();
    expect(screen.getByText(/Consumed/i)).toBeInTheDocument();
    expect(screen.getByText("Goals")).toBeInTheDocument();
    expect(screen.getByText("Avoid")).toBeInTheDocument();
  });
});
