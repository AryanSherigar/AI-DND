import React, { useState } from "react";
import { ExpandablePanelProps } from "./ExpandablePanel.types";

export const ExpandablePanel: React.FC<ExpandablePanelProps> = ({
  summary,
  actions,
  children,
  defaultExpanded = false,
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const handleToggle = (): void => setIsExpanded((current) => !current);

  return (
    <div className="border border-zinc-800 bg-zinc-900 px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={handleToggle}
          aria-expanded={isExpanded}
          className="flex flex-1 items-center gap-2 text-left"
        >
          <span
            className={`text-zinc-500 transition-transform ${isExpanded ? "rotate-90" : ""}`}
            aria-hidden="true"
          >
            ▸
          </span>
          <span className="min-w-0 flex-1">{summary}</span>
        </button>
        {actions && (
          <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>
        )}
      </div>
      {isExpanded && (
        <div className="mt-3 border-t border-zinc-800 pt-3">{children}</div>
      )}
    </div>
  );
};
