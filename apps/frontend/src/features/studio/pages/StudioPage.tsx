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
    <div className="flex min-h-0 flex-1 flex-col font-sans text-content">
      <header className="flex flex-shrink-0 items-center justify-between border-b border-border-subtle px-6 pb-4 pt-16">
        <h1 className="font-mono text-sm font-semibold uppercase tracking-widest text-content">
          Studio
        </h1>
        <Button variant="primary" onClick={handleNewScenario}>
          New scenario
        </Button>
      </header>

      <main className="custom-scrollbar min-h-0 flex-1 overflow-y-auto px-6 py-8">
        {isLoading && (
          <div className="flex h-full items-center justify-center font-mono text-sm uppercase tracking-wider text-content-faint">
            Loading scenarios…
          </div>
        )}

        {!isLoading && error && (
          <div className="flex h-full items-center justify-center font-mono text-sm uppercase tracking-wider text-danger">
            Failed to load your scenarios.
          </div>
        )}

        {!isLoading && !error && scenarios.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <p className="font-mono text-sm uppercase tracking-wider text-content-faint">
              No scenarios yet.
            </p>
            <Button variant="primary" onClick={handleNewScenario}>
              New scenario
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
        <p className="font-sans text-sm text-content-muted">
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
