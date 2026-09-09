import React, { useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { useScenario } from "../hooks/useScenario";
import { useStudioStore } from "../stores/studio.store";
import { StudioDocumentLayout } from "../components/Layout/StudioDocumentLayout";
import { MasterModeStudioLayout } from "../components/Layout/MasterModeStudioLayout";

import { SaveStatusIndicator } from "../components/SaveStatusIndicator/SaveStatusIndicator";

export const EditScenarioPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { scenario, isLoading, error } = useScenario(id ?? null);
  const setMode = useStudioStore((s) => s.setMode);
  const hydrateFromScenario = useStudioStore((s) => s.hydrateFromScenario);
  const isSaving = useStudioStore((s) => s.isSaving);
  const lastSaved = useStudioStore((s) => s.lastSaved);

  useEffect(() => {
    if (scenario) {
      setMode(scenario.mode);
      if (scenario.mode === "newbie") {
        hydrateFromScenario(scenario);
      }
    }
  }, [scenario, setMode, hydrateFromScenario]);

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
    <div className="flex h-screen flex-col overflow-hidden bg-surface-sunken font-sans text-content">
      <header className="z-50 flex flex-shrink-0 items-center justify-between gap-4 bg-surface-sunken px-5 py-2">
        <div className="flex min-w-0 items-center gap-5">
          <Link
            to="/"
            className="shrink-0 font-mono text-sm font-semibold lowercase tracking-[0.25em] text-content transition-colors hover:text-accent"
          >
            wevr
          </Link>
          <nav className="hidden shrink-0 items-center gap-1 lg:flex">
            <Link
              to="/"
              className="rounded-md px-2.5 py-1.5 font-sans text-sm text-content-muted transition-colors hover:text-content"
            >
              Home
            </Link>
            <Link
              to="/discover"
              className="rounded-md px-2.5 py-1.5 font-sans text-sm text-content-muted transition-colors hover:text-content"
            >
              Discover
            </Link>
            <Link
              to="/studio"
              className="rounded-md px-2.5 py-1.5 font-sans text-sm text-content transition-colors hover:text-content"
            >
              Studio
            </Link>
          </nav>
          <h1 className="truncate font-mono text-sm font-semibold uppercase tracking-widest text-content-faint">
            {scenario.title || "Untitled scenario"}
          </h1>
        </div>
        <div className="flex items-center gap-4 font-mono text-xs uppercase tracking-wider">
          <SaveStatusIndicator isSaving={isSaving} lastSaved={lastSaved} />
          <span className="shrink-0 text-content-faint">
            {scenario.mode === "master" ? "Master mode" : "Newbie mode"}
          </span>
        </div>
      </header>
      <main className="flex-1 flex flex-col relative min-h-0">
        {scenario.mode === "master" ? (
          <MasterModeStudioLayout scenarioId={id} />
        ) : (
          <StudioDocumentLayout scenarioId={id} />
        )}
      </main>
    </div>
  );
};
