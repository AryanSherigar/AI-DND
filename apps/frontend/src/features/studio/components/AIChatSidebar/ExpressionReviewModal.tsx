import React, { useMemo } from "react";
import { Modal } from "@/shared/components/ui/Modal";
import { SelectOption } from "@/shared/components/ui/Select";
import { useEntities } from "../../hooks/useEntities";
import { useScenario } from "../../hooks/useScenario";
import { useConditions } from "../../hooks/useConditions";
import { useInvariants } from "../../hooks/useInvariants";
import { useEndConditions } from "../../hooks/useEndConditions";
import { ConditionResponse } from "../../types/condition.types";
import { InvariantResponse } from "../../types/invariant.types";
import { EndConditionResponse } from "../../types/end_condition.types";
import { buildAvailableFields } from "../ConditionEditor/ExpressionBuilder/availableFields";
import { ConditionForm } from "../ConditionEditor/ConditionForm";
import { InvariantForm } from "../InvariantEditor/InvariantForm";
import { EndConditionForm } from "../EndConditionsEditor/EndConditionForm";

export type ExpressionReviewTarget =
  "condition" | "invariant" | "end_condition";

export interface ExpressionReviewModalProps {
  target: ExpressionReviewTarget | null;
  scenarioId: string;
  draft: Record<string, unknown> | null;
  onClose: () => void;
  onApplied: () => void;
}

const FIXED_APPLIES_TO_OPTIONS: SelectOption[] = [
  { value: "global", label: "Global" },
  { value: "player", label: "Player" },
];

const asConditionDraft = (
  draft: Record<string, unknown> | null,
): ConditionResponse | null => {
  if (!draft) return null;
  return {
    condition_id: "",
    scenario_id: "",
    label: (draft.label as string) ?? "",
    condition_expression:
      (draft.condition_expression as Record<string, unknown>) ?? {},
    condition_version: "1.0",
    narrator_instruction: (draft.narrator_instruction as string) ?? "",
    metadata: {},
    state_mutation:
      (draft.state_mutation as ConditionResponse["state_mutation"]) ?? null,
  };
};

const asInvariantDraft = (
  draft: Record<string, unknown> | null,
): InvariantResponse | null => {
  if (!draft) return null;
  return {
    invariant_id: "",
    scenario_id: "",
    label: (draft.label as string) ?? "",
    invariant_expression:
      (draft.invariant_expression as Record<string, unknown>) ?? {},
    applies_to: (draft.applies_to as string) ?? "global",
    narrator_text: (draft.narrator_text as string) ?? "",
  };
};

const asEndConditionDraft = (
  draft: Record<string, unknown> | null,
): EndConditionResponse | null => {
  if (!draft) return null;
  return {
    end_condition_id: "",
    scenario_id: "",
    condition_expression:
      (draft.condition_expression as Record<string, unknown>) ?? {},
    outcome_tag:
      (draft.outcome_tag as EndConditionResponse["outcome_tag"]) ?? "win",
    outcome_title: (draft.outcome_title as string) ?? "",
    outcome_text: (draft.outcome_text as string) ?? "",
    is_secret: (draft.is_secret as boolean) ?? false,
    priority: 0,
  };
};

const TITLE_BY_TARGET: Record<ExpressionReviewTarget, string> = {
  condition: "Review Suggested Active Rule",
  invariant: "Review Suggested Always-True Rule",
  end_condition: "Review Suggested Win/Lose Condition",
};

export const ExpressionReviewModal: React.FC<ExpressionReviewModalProps> = ({
  target,
  scenarioId,
  draft,
  onClose,
  onApplied,
}) => {
  const { scenario } = useScenario(scenarioId);
  const { entities } = useEntities(scenarioId);
  const conditionsHook = useConditions(scenarioId);
  const invariantsHook = useInvariants(scenarioId);
  const endConditionsHook = useEndConditions(scenarioId);

  const availableFields = useMemo(
    () => buildAvailableFields(scenario?.state_schema ?? {}, entities),
    [scenario, entities],
  );

  const appliesToOptions = useMemo<SelectOption[]>(
    () => [
      ...FIXED_APPLIES_TO_OPTIONS,
      ...entities.map((entity) => ({
        value: entity.entity_id,
        label: entity.canonical_name,
      })),
    ],
    [entities],
  );

  return (
    <Modal
      isOpen={target !== null}
      onClose={onClose}
      title={target ? TITLE_BY_TARGET[target] : undefined}
    >
      {target === "condition" && (
        <ConditionForm
          condition={asConditionDraft(draft)}
          availableFields={availableFields}
          onSubmit={(payload) =>
            conditionsHook.createCondition(payload, { onSuccess: onApplied })
          }
          onCancel={onClose}
          isSubmitting={conditionsHook.isCreating}
          submitError={conditionsHook.createError}
        />
      )}
      {target === "invariant" && (
        <InvariantForm
          invariant={asInvariantDraft(draft)}
          availableFields={availableFields}
          appliesToOptions={appliesToOptions}
          onSubmit={(payload) =>
            invariantsHook.createInvariant(payload, { onSuccess: onApplied })
          }
          onCancel={onClose}
          isSubmitting={invariantsHook.isCreating}
          submitError={invariantsHook.createError}
        />
      )}
      {target === "end_condition" && (
        <EndConditionForm
          endCondition={asEndConditionDraft(draft)}
          availableFields={availableFields}
          onSubmit={(payload) =>
            endConditionsHook.createEndCondition(payload, {
              onSuccess: onApplied,
            })
          }
          onCancel={onClose}
          isSubmitting={endConditionsHook.isCreating}
          submitError={endConditionsHook.createError}
        />
      )}
    </Modal>
  );
};
