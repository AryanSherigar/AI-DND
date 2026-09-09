import React from "react";
import { SaveStatusIndicatorProps } from "./SaveStatusIndicator.types";

export const SaveStatusIndicator: React.FC<SaveStatusIndicatorProps> = ({
  isSaving,
  lastSaved,
}) => {
  if (isSaving) {
    return (
      <span className="flex items-center gap-2 text-content-muted">
        <span className="h-3 w-3 animate-spin rounded-full border-b-2 border-content-muted" />
        Saving…
      </span>
    );
  }
  if (lastSaved) {
    return <span className="text-success">Saved</span>;
  }
  return <span className="text-content-faint">All changes saved</span>;
};
