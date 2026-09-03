import React from "react";
import { useParams } from "react-router-dom";
import { useScenario } from "../hooks/useScenario";
import { StudioDocumentLayout } from "../components/Layout/StudioDocumentLayout";
import { MasterModeStudioLayout } from "../components/Layout/MasterModeStudioLayout";

export const EditScenarioPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { scenario, isLoading, error } = useScenario(id ?? null);

  if (!id) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center text-zinc-400">
        No scenario ID provided.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center text-zinc-400">
        Loading scenario…
      </div>
    );
  }

  if (error || !scenario) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center text-red-400">
        Failed to load scenario.
      </div>
    );
  }

  return (
    <div className="h-screen overflow-hidden bg-zinc-950 text-zinc-100 flex flex-col font-sans">
      <header className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-950 flex-shrink-0 z-50">
        <h1 className="text-sm font-semibold text-zinc-100 tracking-widest uppercase font-mono truncate">
          {scenario.title || "Untitled Scenario"}
        </h1>
        <span className="text-xs uppercase tracking-wider text-zinc-500 font-mono">
          {scenario.mode === "master" ? "Master Mode" : "Newbie Mode"}
        </span>
      </header>
      <main className="flex-1 flex flex-col relative min-h-0">
        {scenario.mode === "master" ? (
          <MasterModeStudioLayout scenarioId={id} />
        ) : (
          <StudioDocumentLayout />
        )}
      </main>
    </div>
  );
};
