import React from "react";
import { Button } from "@/shared/components/ui/Button";
import { Card } from "@/shared/components/ui/Card";
import { Input } from "@/shared/components/ui/Input";
import { CheckpointPersonaOverride } from "./NarratorPersonaEditor.types";

interface CheckpointOverrideRowProps {
  override: CheckpointPersonaOverride;
  onChange: (override: CheckpointPersonaOverride) => void;
  onRemove: () => void;
}

export const CheckpointOverrideRow: React.FC<CheckpointOverrideRowProps> = ({
  override,
  onChange,
  onRemove,
}) => {
  return (
    <Card className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-zinc-500">
          {override.checkpoint_id}
        </span>
        <Button type="button" variant="ghost" size="sm" onClick={onRemove}>
          Remove
        </Button>
      </div>
      <Input
        aria-label="Trigger description"
        placeholder="After the player enters the Hollow Cairn"
        value={override.trigger_description}
        onChange={(e) =>
          onChange({ ...override, trigger_description: e.target.value })
        }
      />
      <Input
        aria-label="Persona override"
        placeholder="Narrate with a grim, foreboding tone"
        value={override.persona_override}
        onChange={(e) =>
          onChange({ ...override, persona_override: e.target.value })
        }
      />
    </Card>
  );
};
