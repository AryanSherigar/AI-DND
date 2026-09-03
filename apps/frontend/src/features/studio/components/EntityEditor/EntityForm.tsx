import React, { useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { Select } from "@/shared/components/ui/Select";
import { ENTITY_TYPES, EntityType } from "../../types/entity.types";
import { AttributesSchemaEditor } from "./AttributesSchemaEditor";
import { EntityFormProps, EntityFormState } from "./EntityForm.types";

const ENTITY_TYPE_OPTIONS = ENTITY_TYPES.map((type) => ({
  value: type,
  label: type,
}));

const buildInitialState = (
  entity: EntityFormProps["entity"],
): EntityFormState => ({
  entityType: entity?.entity_type ?? "character",
  canonicalName: entity?.canonical_name ?? "",
  aliasesText: entity?.aliases.join(", ") ?? "",
  description: entity?.description ?? "",
  obtainable: entity?.obtainable ?? false,
  narratorInstruction: entity?.narrator_instruction ?? "",
  attributesSchema: entity?.attributes_schema ?? {},
});

const parseAliases = (aliasesText: string): string[] =>
  aliasesText
    .split(",")
    .map((alias) => alias.trim())
    .filter(Boolean);

export const EntityForm: React.FC<EntityFormProps> = ({
  entity,
  onSubmit,
  onCancel,
  isSubmitting,
  submitError,
}) => {
  const [formState, setFormState] = useState<EntityFormState>(() =>
    buildInitialState(entity),
  );
  const isItemType = formState.entityType === "item";

  const handleSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    onSubmit({
      entity_type: formState.entityType,
      canonical_name: formState.canonicalName,
      aliases: parseAliases(formState.aliasesText),
      description: formState.description || undefined,
      obtainable: isItemType ? formState.obtainable : undefined,
      narrator_instruction: formState.narratorInstruction || undefined,
      attributes_schema: formState.attributesSchema,
    });
  };

  const handleTypeChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ): void => {
    setFormState({
      ...formState,
      entityType: event.target.value as EntityType,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <Select
        aria-label="Entity type"
        options={ENTITY_TYPE_OPTIONS}
        value={formState.entityType}
        onChange={handleTypeChange}
      />
      <Input
        value={formState.canonicalName}
        onChange={(e) =>
          setFormState({ ...formState, canonicalName: e.target.value })
        }
        placeholder="Canonical name"
        required
      />
      <Input
        value={formState.aliasesText}
        onChange={(e) =>
          setFormState({ ...formState, aliasesText: e.target.value })
        }
        placeholder="Aliases (comma-separated)"
      />
      <textarea
        value={formState.description}
        onChange={(e) =>
          setFormState({ ...formState, description: e.target.value })
        }
        placeholder="Description"
        className="w-full border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-300"
        rows={3}
      />
      {isItemType && (
        <label className="flex items-center gap-2 text-sm text-zinc-300">
          <input
            type="checkbox"
            checked={formState.obtainable}
            onChange={(e) =>
              setFormState({ ...formState, obtainable: e.target.checked })
            }
          />
          Obtainable
        </label>
      )}
      <textarea
        value={formState.narratorInstruction}
        onChange={(e) =>
          setFormState({ ...formState, narratorInstruction: e.target.value })
        }
        placeholder="Narrator instruction"
        className="w-full border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-300"
        rows={2}
      />
      <AttributesSchemaEditor
        value={formState.attributesSchema}
        onChange={(attributesSchema) =>
          setFormState({ ...formState, attributesSchema })
        }
      />
      {submitError && <p className="text-xs text-red-400">{submitError}</p>}
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : "Save"}
        </Button>
      </div>
    </form>
  );
};
