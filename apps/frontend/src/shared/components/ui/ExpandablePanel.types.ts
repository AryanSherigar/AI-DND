import React from "react";

export interface ExpandablePanelProps {
  summary: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  defaultExpanded?: boolean;
}
