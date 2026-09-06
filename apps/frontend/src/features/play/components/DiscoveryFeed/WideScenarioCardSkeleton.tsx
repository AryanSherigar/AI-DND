import React from "react";

export const WideScenarioCardSkeleton: React.FC = () => {
  return (
    <div className="flex animate-pulse flex-col gap-4 rounded-2xl border border-transparent p-3 md:flex-row md:gap-8 md:p-4">
      <div className="aspect-video w-full shrink-0 rounded-xl bg-surface md:w-80 lg:w-96" />
      <div className="flex flex-1 flex-col justify-center gap-3">
        <div className="h-7 w-2/3 rounded bg-surface" />
        <div className="h-3 w-1/3 rounded bg-surface" />
        <div className="h-3 w-full rounded bg-surface" />
        <div className="h-3 w-5/6 rounded bg-surface" />
      </div>
    </div>
  );
};
