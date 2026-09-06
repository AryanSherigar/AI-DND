import React, { useState } from "react";
import { TabHelpBannerProps } from "./TabHelpBanner.types";

export const TabHelpBanner: React.FC<TabHelpBannerProps> = ({ helpText }) => {
  const [isDismissed, setIsDismissed] = useState(false);

  if (isDismissed) return null;

  const handleDismiss = (): void => setIsDismissed(true);

  return (
    <div className="rounded-md mb-4 flex items-start justify-between gap-3 border border-border-subtle bg-surface px-3 py-2 text-xs text-content-muted">
      <p>{helpText}</p>
      <button
        type="button"
        onClick={handleDismiss}
        aria-label="Dismiss help"
        className="flex-shrink-0 text-content-faint hover:text-content-muted"
      >
        ✕
      </button>
    </div>
  );
};
