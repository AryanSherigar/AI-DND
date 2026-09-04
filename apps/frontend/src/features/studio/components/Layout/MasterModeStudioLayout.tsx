import React from "react";
import { EntityEditor } from "../EntityEditor/EntityEditor";
import { FactEditor } from "../FactEditor/FactEditor";
import { ConditionEditor } from "../ConditionEditor/ConditionEditor";
import { StateSchemaEditor } from "../StateSchemaEditor/StateSchemaEditor";
import { EndConditionsEditor } from "../EndConditionsEditor/EndConditionsEditor";
import { InvariantEditor } from "../InvariantEditor/InvariantEditor";
import { PlaytestButton } from "../PlaytestButton/PlaytestButton";
import { DuplicateScenarioButton } from "../DuplicateScenarioButton/DuplicateScenarioButton";
import { StudioChatDrawer } from "./StudioChatDrawer";
import { StudioSetupPanel } from "./StudioSetupPanel";
import { TabHelpBanner } from "./TabHelpBanner";
import {
  MASTER_MODE_TABS,
  MasterModeStudioLayoutProps,
  MasterModeTabId,
} from "./MasterModeStudioLayout.types";
import { useStudioStore } from "../../stores/studio.store";

export const MasterModeStudioLayout: React.FC<MasterModeStudioLayoutProps> = ({
  scenarioId,
}) => {
  const activeTab = useStudioStore((state) => state.activeMasterTab);
  const setActiveTab = useStudioStore((state) => state.setActiveMasterTab);

  const handleTabClick = (tabId: MasterModeTabId) => () => setActiveTab(tabId);
  const activeTabConfig = MASTER_MODE_TABS.find((tab) => tab.id === activeTab);

  return (
    <div className="flex flex-1 overflow-hidden bg-zinc-950 font-sans text-zinc-300">
      <nav className="w-56 border-r border-zinc-800 flex-shrink-0 p-4 space-y-1">
        {MASTER_MODE_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={handleTabClick(tab.id)}
            className={`w-full text-left px-3 py-2 text-sm ${
              activeTab === tab.id
                ? "bg-zinc-900 text-zinc-100 font-medium"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {tab.label}
          </button>
        ))}
        <div className="pt-4 space-y-2 border-t border-zinc-800 mt-4">
          <PlaytestButton scenarioId={scenarioId} />
          <DuplicateScenarioButton scenarioId={scenarioId} />
        </div>
      </nav>
      <main className="flex-1 overflow-y-auto p-8">
        {activeTabConfig && (
          <TabHelpBanner key={activeTab} helpText={activeTabConfig.helpText} />
        )}
        {activeTab === "entities" && <EntityEditor scenarioId={scenarioId} />}
        {activeTab === "facts" && <FactEditor scenarioId={scenarioId} />}
        {activeTab === "state" && <StateSchemaEditor scenarioId={scenarioId} />}
        {activeTab === "conditions" && (
          <ConditionEditor scenarioId={scenarioId} />
        )}
        {activeTab === "invariants" && (
          <InvariantEditor scenarioId={scenarioId} />
        )}
        {activeTab === "endings" && (
          <EndConditionsEditor scenarioId={scenarioId} />
        )}
        {activeTab === "setup" && <StudioSetupPanel scenarioId={scenarioId} />}
      </main>
      <StudioChatDrawer />
    </div>
  );
};
