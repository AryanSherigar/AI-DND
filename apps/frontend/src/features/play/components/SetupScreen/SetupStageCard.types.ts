import { ScenarioDetailResponse, ScenarioMock } from "../../types/scenario";

export interface NormalizedSetupField {
  id: string;
  key: string;
  label: string;
  type: string;
  description?: string;
  placeholder?: string;
  required?: boolean;
  options: Array<{ id: string; label: string; value: string }>;
  defaultValue?: unknown;
  is_character_name?: boolean;
  predicate?: string;
}

export type SetupScenarioData =
  | ScenarioDetailResponse
  | ScenarioMock
  | {
      id?: string;
      scenario_id?: string;
      title?: string;
      setup_schema?: unknown[];
      setupInputs?: unknown[];
    };

export interface SetupStageCardProps {
  scenario: SetupScenarioData;
  isSubmitting?: boolean;
  onSubmit: (
    formattedPayload: string,
    formValues: Record<string, unknown>,
  ) => void;
}
