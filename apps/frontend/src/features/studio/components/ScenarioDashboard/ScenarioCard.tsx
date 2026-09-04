import React from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "@/shared/components/ui/Card";
import { Badge, BadgeVariant } from "@/shared/components/ui/Badge";
import { Button } from "@/shared/components/ui/Button";
import { DuplicateScenarioButton } from "../DuplicateScenarioButton/DuplicateScenarioButton";
import { ScenarioSummaryResponse } from "../../types/scenario.types";
import { ScenarioCardProps } from "./ScenarioDashboard.types";

const STATUS_BADGE_VARIANT: Record<
  ScenarioSummaryResponse["status"],
  BadgeVariant
> = {
  draft: "default",
  publishing: "warning",
  published: "success",
  publish_failed: "danger",
  archived: "default",
};

export const ScenarioCard: React.FC<ScenarioCardProps> = ({
  scenario,
  onDelete,
  isDeleting,
}) => {
  const navigate = useNavigate();

  const handleEdit = (): void => {
    navigate(`/studio/${scenario.scenario_id}/edit`);
  };

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <h2 className="truncate font-mono text-sm font-semibold uppercase tracking-wide text-zinc-100">
          {scenario.title || "Untitled Scenario"}
        </h2>
        <Badge variant={STATUS_BADGE_VARIANT[scenario.status]}>
          {scenario.status}
        </Badge>
      </div>

      <p className="line-clamp-2 min-h-[2.5rem] text-sm text-zinc-400">
        {scenario.logline || "No logline yet."}
      </p>

      <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-zinc-500">
        <span className="font-mono">
          {scenario.mode === "master" ? "Master Mode" : "Newbie Mode"}
        </span>
        <span>·</span>
        <span>{new Date(scenario.updated_at).toLocaleDateString()}</span>
      </div>

      <div className="mt-auto flex items-center gap-2 pt-2">
        <Button variant="primary" size="sm" onClick={handleEdit}>
          Edit
        </Button>
        <DuplicateScenarioButton scenarioId={scenario.scenario_id} />
        <Button
          variant="danger"
          size="sm"
          disabled={isDeleting}
          onClick={() => onDelete(scenario.scenario_id)}
        >
          {isDeleting ? "Deleting..." : "Delete"}
        </Button>
      </div>
    </Card>
  );
};
