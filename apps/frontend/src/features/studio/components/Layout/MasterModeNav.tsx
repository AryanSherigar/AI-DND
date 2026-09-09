import React from "react";
import { PlaytestButton } from "../PlaytestButton/PlaytestButton";
import { DuplicateScenarioButton } from "../DuplicateScenarioButton/DuplicateScenarioButton";
import {
  MASTER_MODE_TABS,
  MasterModeNavProps,
  MasterModeTabId,
} from "./MasterModeStudioLayout.types";

export const MasterModeNav: React.FC<MasterModeNavProps> = ({
  scenarioId,
  activeTab,
  onTabSelect,
}) => {
  const handleTabClick = (tabId: MasterModeTabId) => (): void => {
    onTabSelect(tabId);
  };

  return (
    <nav className="w-56 border-r border-border-subtle flex-shrink-0 p-4 space-y-1">
      {MASTER_MODE_TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={handleTabClick(tab.id)}
          className={`w-full text-left px-3 py-2 text-sm ${
            activeTab === tab.id
              ? "bg-surface text-content font-medium"
              : "text-content-faint hover:text-content-muted"
          }`}
        >
          {tab.label}
        </button>
      ))}
      <div className="pt-4 space-y-2 border-t border-border-subtle mt-4">
        <PlaytestButton scenarioId={scenarioId} />
        <DuplicateScenarioButton scenarioId={scenarioId} />
      </div>
    </nav>
  );
};
