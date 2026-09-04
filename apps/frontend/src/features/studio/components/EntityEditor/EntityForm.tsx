import React, { useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { Select, SelectOption } from "@/shared/components/ui/Select";
import { useEntityTypeChangePreview } from "../../hooks/useEntityTypeChangePreview";
import { useScenarioEntityTypes } from "../../hooks/useScenarioEntityTypes";
import {
  ENTITY_TYPES,
  EntityTypeChangePreviewResponse,
} from "../../types/entity.types";
import { AttributesSchemaEditor } from "./AttributesSchemaEditor";
import { CustomEntityTypeForm } from "./CustomEntityTypeForm";
import { EntityFormProps, EntityFormState } from "./EntityForm.types";
import { EntityTypeChangeWarningModal } from "./EntityTypeChangeWarningModal";

const NEW_CUSTOM_TYPE_VALUE = "__new_custom_type__";
const NEW_CUSTOM_TYPE_OPTION: SelectOption = {
  value: NEW_CUSTOM_TYPE_VALUE,
  label: "+ New custom type…",
};

interface PendingTypeChange {
  entityType: string;
  label: string;
  preview: EntityTypeChangePreviewResponse;
}

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
  scenarioId,
  entity,
  onSubmit,
  onCancel,
  isSubmitting,
  submitError,
}) => {
  const { entityTypes, createEntityTypeAsync } =
    useScenarioEntityTypes(scenarioId);
  const { previewTypeChange } = useEntityTypeChangePreview(scenarioId);

  const [formState, setFormState] = useState<EntityFormState>(() =>
    buildInitialState(entity),
  );
  const [customTypeKey, setCustomTypeKey] = useState("");
  const [customTypeLabel, setCustomTypeLabel] = useState("");
  const [customTypeAttributesSchema, setCustomTypeAttributesSchema] = useState<
    EntityFormState["attributesSchema"]
  >({});
  const [pendingTypeChange, setPendingTypeChange] =
    useState<PendingTypeChange | null>(null);
  const [isSavingCustomType, setIsSavingCustomType] = useState(false);

  const isNewCustomType = formState.entityType === NEW_CUSTOM_TYPE_VALUE;
  const isItemType = formState.entityType === "item";

  const entityTypeOptions: SelectOption[] = [
    ...ENTITY_TYPES.map((type) => ({ value: type, label: type })),
    ...entityTypes.map((type) => ({
      value: type.type_key,
      label: type.display_label,
    })),
    NEW_CUSTOM_TYPE_OPTION,
  ];

  const resolveOptionLabel = (value: string): string =>
    entityTypeOptions.find((option) => option.value === value)?.label ?? value;

  const handleTypeSelectChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ): void => {
    const nextType = event.target.value;
    if (
      nextType === NEW_CUSTOM_TYPE_VALUE ||
      !entity ||
      nextType === entity.entity_type
    ) {
      setFormState({ ...formState, entityType: nextType });
      return;
    }

    previewTypeChange(
      { entityId: entity.entity_id, newEntityType: nextType },
      {
        onSuccess: (preview) => {
          if (preview.dropped_fields.length === 0) {
            setFormState((current) => ({ ...current, entityType: nextType }));
            return;
          }
          setPendingTypeChange({
            entityType: nextType,
            label: resolveOptionLabel(nextType),
            preview,
          });
        },
      },
    );
  };

  const handleConfirmTypeChange = (): void => {
    if (!pendingTypeChange) return;
    setFormState((current) => ({
      ...current,
      entityType: pendingTypeChange.entityType,
    }));
    setPendingTypeChange(null);
  };

  const handleCancelTypeChange = (): void => setPendingTypeChange(null);

  const handleSubmit = async (event: React.FormEvent): Promise<void> => {
    event.preventDefault();

    let finalEntityType = formState.entityType;
    let finalAttributesSchema = formState.attributesSchema;

    if (isNewCustomType) {
      if (!customTypeLabel.trim() || !customTypeKey) return;
      setIsSavingCustomType(true);
      try {
        const created = await createEntityTypeAsync({
          type_key: customTypeKey,
          display_label: customTypeLabel,
          attributes_schema: customTypeAttributesSchema,
        });
        finalEntityType = created.type_key;
        finalAttributesSchema = {
          ...customTypeAttributesSchema,
          ...formState.attributesSchema,
        };
      } finally {
        setIsSavingCustomType(false);
      }
    }

    onSubmit({
      entity_type: finalEntityType,
      canonical_name: formState.canonicalName,
      aliases: parseAliases(formState.aliasesText),
      description: formState.description || undefined,
      obtainable: finalEntityType === "item" ? formState.obtainable : undefined,
      narrator_instruction: formState.narratorInstruction || undefined,
      attributes_schema: finalAttributesSchema,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <Select
        aria-label="Entity type"
        options={entityTypeOptions}
        value={formState.entityType}
        onChange={handleTypeSelectChange}
      />
      {isNewCustomType && (
        <CustomEntityTypeForm
          typeKey={customTypeKey}
          displayLabel={customTypeLabel}
          attributesSchema={customTypeAttributesSchema}
          onTypeKeyChange={setCustomTypeKey}
          onDisplayLabelChange={setCustomTypeLabel}
          onAttributesSchemaChange={setCustomTypeAttributesSchema}
        />
      )}
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
      {isItemType && !isNewCustomType && (
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
      {!isNewCustomType && (
        <AttributesSchemaEditor
          value={formState.attributesSchema}
          onChange={(attributesSchema) =>
            setFormState({ ...formState, attributesSchema })
          }
        />
      )}
      {submitError && <p className="text-xs text-red-400">{submitError}</p>}
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={isSubmitting || isSavingCustomType}>
          {isSubmitting || isSavingCustomType ? "Saving…" : "Save"}
        </Button>
      </div>
      <EntityTypeChangeWarningModal
        isOpen={pendingTypeChange !== null}
        newTypeLabel={pendingTypeChange?.label ?? ""}
        preview={pendingTypeChange?.preview ?? null}
        onConfirm={handleConfirmTypeChange}
        onCancel={handleCancelTypeChange}
      />
    </form>
  );
};
