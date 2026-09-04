import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/shared/components/ui/Button";
import { Modal } from "@/shared/components/ui/Modal";
import { useMyScenarios } from "../hooks/useMyScenarios";
import { ScenarioCard } from "../components/ScenarioDashboard/ScenarioCard";

export const StudioPage: React.FC = () => {
  const navigate = useNavigate();
  const { scenarios, isLoading, error, deleteScenario, isDeleting } =
    useMyScenarios();
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const handleNewScenario = (): void => {
    navigate("/studio/new");
  };

  const handleConfirmDelete = (): void => {
    if (!pendingDeleteId) return;
    deleteScenario(pendingDeleteId);
    setPendingDeleteId(null);
  };

  return (
    <div className="h-screen overflow-hidden bg-zinc-950 text-zinc-100 flex flex-col font-sans">
      <header className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-950 flex-shrink-0 z-50">
        <h1 className="text-sm font-semibold text-zinc-100 tracking-widest uppercase font-mono">
          AI-DND Studio
        </h1>
        <Button variant="primary" onClick={handleNewScenario}>
          + New Scenario
        </Button>
      </header>

      <main className="flex-1 overflow-y-auto min-h-0 px-6 py-8">
        {isLoading && (
          <div className="flex h-full items-center justify-center text-zinc-500 font-mono text-sm uppercase tracking-wider">
            Loading scenarios…
          </div>
        )}

        {!isLoading && error && (
          <div className="flex h-full items-center justify-center text-red-400 font-mono text-sm uppercase tracking-wider">
            Failed to load your scenarios.
          </div>
        )}

        {!isLoading && !error && scenarios.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <p className="text-zinc-500 font-mono text-sm uppercase tracking-wider">
              You haven&apos;t created any scenarios yet.
            </p>
            <Button variant="primary" onClick={handleNewScenario}>
              + New Scenario
            </Button>
          </div>
        )}

        {!isLoading && !error && scenarios.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {scenarios.map((scenario) => (
              <ScenarioCard
                key={scenario.scenario_id}
                scenario={scenario}
                onDelete={setPendingDeleteId}
                isDeleting={isDeleting}
              />
            ))}
          </div>
        )}
      </main>

      <Modal
        isOpen={pendingDeleteId !== null}
        onClose={() => setPendingDeleteId(null)}
        title="Delete Scenario"
      >
        <p className="text-sm text-zinc-400">
          This will permanently delete the scenario draft, or archive it if
          published. This action cannot be undone.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setPendingDeleteId(null)}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleConfirmDelete}>
            Delete
          </Button>
        </div>
      </Modal>
    </div>
  );
};
