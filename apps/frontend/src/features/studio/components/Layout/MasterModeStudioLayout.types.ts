export const MASTER_MODE_TABS = [
  { id: "entities", label: "Entities" },
  { id: "facts", label: "Facts" },
  { id: "state", label: "State Schema" },
  { id: "conditions", label: "Active Conditions" },
  { id: "invariants", label: "World Rules" },
  { id: "endings", label: "Endings" },
  { id: "setup", label: "Setup & Narrator" },
] as const;

export type MasterModeTabId = (typeof MASTER_MODE_TABS)[number]["id"];

export interface MasterModeStudioLayoutProps {
  scenarioId: string;
}

export interface StudioSetupPanelProps {
  scenarioId: string;
}
