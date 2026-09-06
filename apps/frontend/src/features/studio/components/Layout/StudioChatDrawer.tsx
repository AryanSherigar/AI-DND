import React, { useState } from "react";
import { AIChatSidebar } from "../AIChatSidebar/AIChatSidebar";

export interface StudioChatDrawerProps {
  activeSection?: string;
  scenarioId?: string;
}

export const StudioChatDrawer: React.FC<StudioChatDrawerProps> = ({
  activeSection = "meta",
  scenarioId,
}) => {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  return (
    <>
      {!isDrawerOpen && (
        <button
          onClick={() => setIsDrawerOpen(true)}
          className="rounded-md fixed right-0 top-1/2 -translate-y-1/2 bg-surface border border-r-0 border-border-subtle p-2 text-content-faint hover:text-content transition-colors z-40 shadow-xl"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </button>
      )}

      <div
        className={`fixed right-0 top-[69px] h-[calc(100vh-69px)] w-80 bg-surface-inset border-l border-border-subtle transform transition-transform duration-300 z-50 flex flex-col ${
          isDrawerOpen ? "translate-x-0 shadow-2xl" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between p-4 border-b border-border-subtle">
          <h3 className="text-xs font-semibold text-content uppercase tracking-widest">
AERO
          </h3>
          <button
            onClick={() => setIsDrawerOpen(false)}
            className="text-content-faint hover:text-content"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-hidden">
          <AIChatSidebar
            activeSection={activeSection}
            scenarioId={scenarioId}
          />
        </div>
      </div>
    </>
  );
};
