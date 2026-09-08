import React from "react";
import { Button } from "@/shared/components/ui/Button";
import { Card } from "@/shared/components/ui/Card";
import { Input } from "@/shared/components/ui/Input";
import { Select, SelectOption } from "@/shared/components/ui/Select";
import {
  SetupInputField,
  SetupInputOption,
  SetupInputType,
} from "../../stores/studio.store";
import { SetupFieldOptionList } from "./SetupFieldOptionList";

export interface SetupFieldCardProps {
  field: SetupInputField;
  index: number;
  totalCount: number;
  onUpdate: (updates: Partial<SetupInputField>) => void;
  onDelete: () => void;
  onMove: (direction: "up" | "down") => void;
}

const FIELD_TYPE_OPTIONS: SelectOption[] = [
  { value: "text", label: "Short Text" },
  { value: "single_select", label: "Single Select" },
  { value: "multi_select", label: "Multi-Select" },
  { value: "textarea", label: "Long Text" },
  { value: "number", label: "Number" },
];

export const SetupFieldCard: React.FC<SetupFieldCardProps> = ({
  field,
  index,
  totalCount,
  onUpdate,
  onDelete,
  onMove,
}) => {
  const isSelectType =
    field.type === "single_select" || field.type === "multi_select";

  const handleTypeChange = (e: React.ChangeEvent<HTMLSelectElement>): void => {
    onUpdate({ type: e.target.value as SetupInputType });
  };

  const handleOptionsChange = (options: SetupInputOption[]): void => {
    onUpdate({ options });
  };

  return (
    <Card className="space-y-4 p-4 border border-border-subtle bg-surface">
      <div className="flex items-center justify-between border-b border-border-subtle pb-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-content-faint">
            #{index + 1}
          </span>
          <span className="text-sm font-semibold text-content">
            {field.label || "Untitled Field"}
          </span>
          {field.is_character_name && (
            <span className="text-[10px] text-accent bg-accent/10 px-2 py-0.5 rounded border border-accent/20">
              PROTAGONIST NAME
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={index === 0}
            onClick={() => onMove("up")}
          >
            ↑
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={index === totalCount - 1}
            onClick={() => onMove("down")}
          >
            ↓
          </Button>
          <Button type="button" variant="danger" size="sm" onClick={onDelete}>
            Delete
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="space-y-1">
          <label className="text-xs font-semibold text-content-muted">
            Label
          </label>
          <Input
            aria-label="Field label"
            placeholder="e.g. Character Name"
            value={field.label}
            onChange={(e) => onUpdate({ label: e.target.value })}
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-semibold text-content-muted">
            Key
          </label>
          <Input
            aria-label="Field key"
            placeholder="e.g. character_name"
            value={field.key}
            onChange={(e) => onUpdate({ key: e.target.value })}
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-semibold text-content-muted">
            Type
          </label>
          <Select
            aria-label="Field type"
            options={FIELD_TYPE_OPTIONS}
            value={field.type}
            onChange={handleTypeChange}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
        <div className="space-y-1">
          <label className="flex items-center gap-2 text-xs text-content-muted cursor-pointer">
            <input
              type="checkbox"
              checked={Boolean(field.is_character_name)}
              onChange={(e) =>
                onUpdate({ is_character_name: e.target.checked })
              }
            />
            <span className="font-medium text-content">Is Character Name</span>
          </label>
          <p className="text-[11px] text-content-faint pl-5">
            Binds this input to the protagonist entity&apos;s canonical name.
          </p>
        </div>

        {!field.is_character_name && (
          <div className="space-y-1">
            <label className="text-xs font-semibold text-content-muted">
              Fact Predicate
            </label>
            <Input
              aria-label="Fact predicate"
              placeholder="e.g. has_class, originates_from"
              value={field.predicate || ""}
              onChange={(e) => onUpdate({ predicate: e.target.value })}
            />
            <p className="text-[11px] text-content-faint">
              Attaches as: [Protagonist] [{field.predicate || "has_..."}]
              [Choice]
            </p>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2">
        <label className="flex items-center gap-2 text-xs text-content-muted cursor-pointer">
          <input
            type="checkbox"
            checked={Boolean(field.required)}
            onChange={(e) => onUpdate({ required: e.target.checked })}
          />
          Required Field
        </label>
      </div>

      {isSelectType && (
        <SetupFieldOptionList
          options={field.options || []}
          onChange={handleOptionsChange}
        />
      )}
    </Card>
  );
};
