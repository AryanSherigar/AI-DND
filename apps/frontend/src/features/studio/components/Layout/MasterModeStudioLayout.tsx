import React, { useEffect, useState } from "react";
import { MasterModeNav } from "./MasterModeNav";
import { MasterModeTabPanels } from "./MasterModeTabPanels";
import { StudioChatDrawer } from "./StudioChatDrawer";
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
  const [visitedTabs, setVisitedTabs] = useState<Set<MasterModeTabId>>(
    () => new Set([activeTab]),
  );

  useEffect(() => {
    setVisitedTabs((prev) => {
      if (prev.has(activeTab)) return prev;
      const next = new Set(prev);
      next.add(activeTab);
      return next;
    });
  }, [activeTab]);

  const activeTabConfig = MASTER_MODE_TABS.find((tab) => tab.id === activeTab);

  return (
    <div className="flex flex-1 overflow-hidden bg-surface-inset font-sans text-content-muted">
      <MasterModeNav
        scenarioId={scenarioId}
        activeTab={activeTab}
        onTabSelect={setActiveTab}
      />
      <main className="flex-1 overflow-y-auto p-8">
        {activeTabConfig && (
          <TabHelpBanner key={activeTab} helpText={activeTabConfig.helpText} />
        )}
        <MasterModeTabPanels
          scenarioId={scenarioId}
          activeTab={activeTab}
          visitedTabs={visitedTabs}
        />
      </main>
      <StudioChatDrawer activeSection={activeTab} scenarioId={scenarioId} />
    </div>
  );
};
