import React, { useState } from "react";
import { TabHelpBannerProps } from "./TabHelpBanner.types";

export const TabHelpBanner: React.FC<TabHelpBannerProps> = ({ helpText }) => {
  const [isDismissed, setIsDismissed] = useState(false);

  if (isDismissed) return null;

  const handleDismiss = (): void => setIsDismissed(true);

  return (
    <div className="mb-4 flex items-start justify-between gap-3 border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-zinc-400">
      <p>{helpText}</p>
      <button
        type="button"
        onClick={handleDismiss}
        aria-label="Dismiss help"
        className="flex-shrink-0 text-zinc-600 hover:text-zinc-300"
      >
        ✕
      </button>
    </div>
  );
};
