import React, { useState } from "react";
import { Button } from "@/shared/components/ui/Button";
import { Input } from "@/shared/components/ui/Input";
import { Select, SelectOption } from "@/shared/components/ui/Select";
import { FactFormProps, FactFormState, FactObjectType } from "./FactForm.types";

const NO_SELECTION_OPTION: SelectOption = { value: "", label: "Select…" };

const buildInitialState = (): FactFormState => ({
  subjectEntityId: "",
  predicate: "",
  objectType: "entity",
  objectEntityId: "",
  objectLiteral: "",
  hidden: false,
});

export const FactForm: React.FC<FactFormProps> = ({
  entities,
  onSubmit,
  onCancel,
  isSubmitting,
  submitError,
}) => {
  const [formState, setFormState] = useState<FactFormState>(buildInitialState);
  const entityOptions: SelectOption[] = entities.map((entity) => ({
    value: entity.entity_id,
    label: entity.canonical_name,
  }));
  const isObjectSet =
    Boolean(formState.objectEntityId) ||
    Boolean(formState.objectLiteral.trim());
  const canSubmit =
    Boolean(formState.subjectEntityId) &&
    Boolean(formState.predicate.trim()) &&
    isObjectSet;

  const handleObjectTypeChange = (nextType: FactObjectType): void => {
    setFormState({
      ...formState,
      objectType: nextType,
      objectEntityId: "",
      objectLiteral: "",
    });
  };

  const handleSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    if (!canSubmit) return;
    onSubmit({
      subject_entity_id: formState.subjectEntityId,
      predicate: formState.predicate,
      object_entity_id:
        formState.objectType === "entity"
          ? formState.objectEntityId
          : undefined,
      object_literal:
        formState.objectType === "literal"
          ? formState.objectLiteral
          : undefined,
      hidden: formState.hidden,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <Select
        aria-label="Subject"
        options={[NO_SELECTION_OPTION, ...entityOptions]}
        value={formState.subjectEntityId}
        onChange={(e) =>
          setFormState({ ...formState, subjectEntityId: e.target.value })
        }
      />
      <Input
        value={formState.predicate}
        onChange={(e) =>
          setFormState({ ...formState, predicate: e.target.value })
        }
        placeholder="Predicate"
      />
      <div className="flex gap-2">
        <Button
          type="button"
          variant={formState.objectType === "entity" ? "primary" : "secondary"}
          size="sm"
          onClick={() => handleObjectTypeChange("entity")}
        >
          Entity
        </Button>
        <Button
          type="button"
          variant={formState.objectType === "literal" ? "primary" : "secondary"}
          size="sm"
          onClick={() => handleObjectTypeChange("literal")}
        >
          Literal
        </Button>
      </div>
      {formState.objectType === "entity" ? (
        <Select
          aria-label="Object entity"
          options={[NO_SELECTION_OPTION, ...entityOptions]}
          value={formState.objectEntityId}
          onChange={(e) =>
            setFormState({ ...formState, objectEntityId: e.target.value })
          }
        />
      ) : (
        <Input
          aria-label="Object literal"
          value={formState.objectLiteral}
          onChange={(e) =>
            setFormState({ ...formState, objectLiteral: e.target.value })
          }
          placeholder="Object literal"
        />
      )}
      <label className="flex items-center gap-2 text-sm text-zinc-300">
        <input
          type="checkbox"
          checked={formState.hidden}
          onChange={(e) =>
            setFormState({ ...formState, hidden: e.target.checked })
          }
        />
        Hidden
      </label>
      {!isObjectSet && (
        <p className="text-xs text-amber-400">
          Set either an object entity or a literal value.
        </p>
      )}
      {submitError && <p className="text-xs text-red-400">{submitError}</p>}
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={!canSubmit || isSubmitting}>
          {isSubmitting ? "Saving…" : "Save"}
        </Button>
      </div>
    </form>
  );
};
