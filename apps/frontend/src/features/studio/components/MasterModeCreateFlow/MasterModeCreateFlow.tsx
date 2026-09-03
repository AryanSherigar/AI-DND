import React, { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";
import { createScenario } from "../../api/scenarios.api";

export const MasterModeCreateFlow: React.FC = () => {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");

  const createMutation = useMutation({
    mutationFn: () =>
      createScenario({
        title: title.trim(),
        mode: "master",
        complexity_tier: "master",
      }),
    onSuccess: (scenario) => {
      navigate(`/studio/${scenario.scenario_id}/edit`);
    },
  });

  const handleSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    if (!title.trim() || createMutation.isPending) return;
    createMutation.mutate();
  };

  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <form
        onSubmit={handleSubmit}
        className="max-w-md w-full text-center space-y-4"
      >
        <h2 className="text-2xl font-serif text-zinc-200">Master Mode</h2>
        <p className="text-zinc-400 leading-relaxed">
          Master mode provides full structural control over game state,
          entities, and active conditions.
        </p>
        <Input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Scenario title"
          aria-label="Scenario title"
          autoFocus
        />
        <Button
          type="submit"
          disabled={!title.trim() || createMutation.isPending}
          className="w-full"
        >
          {createMutation.isPending
            ? "Creating…"
            : "Create Master-Mode Scenario"}
        </Button>
        {createMutation.isError && (
          <p className="text-xs text-red-400">
            {extractErrorMessage(
              createMutation.error,
              "Failed to create scenario.",
            )}
          </p>
        )}
      </form>
    </div>
  );
};
