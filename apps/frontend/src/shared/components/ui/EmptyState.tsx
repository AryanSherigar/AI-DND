import React from "react";
import { EmptyStateProps } from "./EmptyState.types";

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  example,
}) => {
  return (
    <div className="border border-dashed border-zinc-800 px-4 py-6 text-center">
      <p className="text-sm font-medium text-zinc-300">{title}</p>
      <p className="mt-1 text-xs text-zinc-500">{description}</p>
      {example && (
        <p className="mt-3 inline-block border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-400">
          {example}
        </p>
      )}
    </div>
  );
};
