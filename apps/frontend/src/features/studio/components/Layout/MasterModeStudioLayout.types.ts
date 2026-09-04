export const MASTER_MODE_TABS = [
  {
    id: "entities",
    label: "People, Places & Things",
    helpText:
      "Entities are the characters, locations, items, and factions the narrator can reference. Give each one a name and, optionally, tracked attributes.",
  },
  {
    id: "facts",
    label: "What's True",
    helpText:
      'Facts are statements the narrator checks and respects during play, e.g. "Hero → owns → Sword". They can link two entities or attach a note to a single one.',
  },
  {
    id: "state",
    label: "Tracked Values",
    helpText:
      "Tracked values are the numbers, flags, and variables that change as the story plays out — health, gold, faction standing, and the like.",
  },
  {
    id: "conditions",
    label: "Active Rules",
    helpText:
      "Active rules watch tracked values and entity facts during play and trigger narrator behavior when they become true.",
  },
  {
    id: "invariants",
    label: "Always-True Rules",
    helpText:
      "Always-true rules are constraints the narrator must never violate, regardless of what else happens in the story.",
  },
  {
    id: "endings",
    label: "Win & Lose Conditions",
    helpText:
      "Win and lose conditions define how a playthrough concludes. Each one has an outcome, a message shown to the player, and an optional trigger.",
  },
  {
    id: "setup",
    label: "Setup & Narrator",
    helpText:
      "Configure the scenario's metadata, opening scene, narrator persona, and other one-time setup details here.",
  },
] as const;

export type MasterModeTabId = (typeof MASTER_MODE_TABS)[number]["id"];

export interface MasterModeStudioLayoutProps {
  scenarioId: string;
}

export interface StudioSetupPanelProps {
  scenarioId: string;
}
