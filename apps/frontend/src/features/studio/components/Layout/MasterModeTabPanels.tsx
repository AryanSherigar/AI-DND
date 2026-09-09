import React from "react";
import { EntityEditor } from "../EntityEditor/EntityEditor";
import { FactEditor } from "../FactEditor/FactEditor";
import { ConditionEditor } from "../ConditionEditor/ConditionEditor";
import { StateSchemaEditor } from "../StateSchemaEditor/StateSchemaEditor";
import { EndConditionsEditor } from "../EndConditionsEditor/EndConditionsEditor";
import { InvariantEditor } from "../InvariantEditor/InvariantEditor";
import { MapEditor } from "../MapEditor/MapEditor";
import { MinigameEditor } from "../MinigameEditor/MinigameEditor";
import { MusicSlotEditor } from "../MusicSlotEditor/MusicSlotEditor";
import { StudioSetupPanel } from "./StudioSetupPanel";
import {
  MasterModeTabId,
  MasterModeTabPanelsProps,
} from "./MasterModeStudioLayout.types";

const getPanelClass = (
  tabId: MasterModeTabId,
  activeTab: MasterModeTabId,
): string => (activeTab === tabId ? "block" : "hidden");

export const MasterModeTabPanels: React.FC<MasterModeTabPanelsProps> = ({
  scenarioId,
  activeTab,
  visitedTabs,
}) => (
  <>
    {visitedTabs.has("entities") && (
      <div className={getPanelClass("entities", activeTab)}>
        <EntityEditor scenarioId={scenarioId} />
      </div>
    )}
    {visitedTabs.has("facts") && (
      <div className={getPanelClass("facts", activeTab)}>
        <FactEditor scenarioId={scenarioId} />
      </div>
    )}
    {visitedTabs.has("state") && (
      <div className={getPanelClass("state", activeTab)}>
        <StateSchemaEditor scenarioId={scenarioId} />
      </div>
    )}
    {visitedTabs.has("conditions") && (
      <div className={getPanelClass("conditions", activeTab)}>
        <ConditionEditor scenarioId={scenarioId} />
      </div>
    )}
    {visitedTabs.has("invariants") && (
      <div className={getPanelClass("invariants", activeTab)}>
        <InvariantEditor scenarioId={scenarioId} />
      </div>
    )}
    {visitedTabs.has("endings") && (
      <div className={getPanelClass("endings", activeTab)}>
        <EndConditionsEditor scenarioId={scenarioId} />
      </div>
    )}
    {visitedTabs.has("minigames") && (
      <div className={getPanelClass("minigames", activeTab)}>
        <MinigameEditor scenarioId={scenarioId} />
      </div>
    )}
    {visitedTabs.has("maps") && (
      <div className={getPanelClass("maps", activeTab)}>
        <MapEditor scenarioId={scenarioId} />
      </div>
    )}
    {visitedTabs.has("music") && (
      <div className={getPanelClass("music", activeTab)}>
        <MusicSlotEditor scenarioId={scenarioId} />
      </div>
    )}
    {visitedTabs.has("setup") && (
      <div className={getPanelClass("setup", activeTab)}>
        <StudioSetupPanel scenarioId={scenarioId} />
      </div>
    )}
  </>
);
