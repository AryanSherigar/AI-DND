import {
  NormalizedSetupField,
  SetupScenarioData,
} from "./SetupStageCard.types";

export const getStringValue = (val: unknown): string => {
  if (typeof val === "string" || typeof val === "number") {
    return String(val);
  }
  return "";
};

export const getArrayValue = (val: unknown): string[] => {
  if (Array.isArray(val)) {
    return val.filter((item): item is string => typeof item === "string");
  }
  return [];
};

export const normalizeOptions = (
  rawOptions: unknown[],
): Array<{ id: string; label: string; value: string }> => {
  return rawOptions.map((opt, optIndex) => {
    if (typeof opt === "string") {
      return { id: `opt-${optIndex}`, label: opt, value: opt };
    }
    const optRecord = (opt && typeof opt === "object" ? opt : {}) as Record<
      string,
      unknown
    >;
    const optLabel = String(
      optRecord.label || optRecord.value || `Option ${optIndex + 1}`,
    );
    const optValue = String(optRecord.value ?? optRecord.label ?? "");
    const optId = String(optRecord.id || `opt-${optIndex}`);
    return { id: optId, label: optLabel, value: optValue };
  });
};

export const normalizeField = (
  f: Record<string, unknown>,
  index: number,
): NormalizedSetupField => {
  const fieldKey = String(f.key || f.field_key || f.id || `field_${index}`);
  const rawOptions = Array.isArray(f.options) ? f.options : [];
  const options = normalizeOptions(rawOptions);
  const isCharacterName = Boolean(
    f.is_character_name || fieldKey === "character_name" || fieldKey === "name",
  );
  return {
    id: fieldKey,
    key: fieldKey,
    label: String(f.label || fieldKey),
    type: String(f.type || "text"),
    description: String(f.description || ""),
    placeholder:
      String(f.placeholder || "") ||
      (isCharacterName ? "Enter your character name..." : ""),
    required: Boolean(f.required) || isCharacterName,
    options,
    defaultValue: f.defaultValue,
    is_character_name: isCharacterName,
    predicate: f.predicate ? String(f.predicate) : undefined,
  };
};

export const getRawSetupSchema = (scenario: SetupScenarioData): unknown[] => {
  if ("setup_schema" in scenario && Array.isArray(scenario.setup_schema)) {
    return scenario.setup_schema;
  }
  if ("setupInputs" in scenario && Array.isArray(scenario.setupInputs)) {
    return scenario.setupInputs;
  }
  return [];
};

export const normalizeSetupFields = (
  scenario: SetupScenarioData,
): NormalizedSetupField[] => {
  const rawFields = getRawSetupSchema(scenario);
  return rawFields
    .filter(
      (f): f is Record<string, unknown> => typeof f === "object" && f !== null,
    )
    .map((f, index) => normalizeField(f, index));
};

export const getInitialFormValues = (
  fields: NormalizedSetupField[],
): Record<string, unknown> => {
  const initialValues: Record<string, unknown> = {};
  fields.forEach((field) => {
    if (field.defaultValue !== undefined) {
      initialValues[field.key] = field.defaultValue;
    } else if (field.type === "multi_select") {
      initialValues[field.key] = [];
    } else if (
      (field.type === "single_select" || field.type === "select") &&
      field.options.length > 0
    ) {
      initialValues[field.key] = field.options[0].value;
    } else {
      initialValues[field.key] = "";
    }
  });
  return initialValues;
};

export const validateSetupForm = (
  fields: NormalizedSetupField[],
  formValues: Record<string, unknown>,
): Record<string, string> => {
  const errors: Record<string, string> = {};
  fields.forEach((field) => {
    if (!field.required) return;
    const val = formValues[field.key];
    if (
      val === undefined ||
      val === "" ||
      (Array.isArray(val) && val.length === 0)
    ) {
      errors[field.key] = `Selection required for ${field.label}`;
    }
  });
  return errors;
};

export const formatSetupSummary = (
  fields: NormalizedSetupField[],
  formValues: Record<string, unknown>,
): string => {
  const lines: string[] = ["\n[PLAYER CHARACTER SETUP]"];
  fields.forEach((field) => {
    const val = formValues[field.key];
    if (val === undefined || val === "") return;

    if (field.type === "single_select" || field.type === "select") {
      const matched = field.options.find((o) => o.value === val);
      lines.push(`- ${field.label}: ${matched ? matched.label : String(val)}`);
    } else if (field.type === "multi_select") {
      const arr = getArrayValue(val);
      const labels = arr
        .map((v) => field.options.find((o) => o.value === v)?.label || v)
        .join(", ");
      lines.push(`- ${field.label}: ${labels}`);
    } else {
      lines.push(`- ${field.label}: ${String(val)}`);
    }
  });
  return lines.join("\n");
};

export const getScenarioIdentifier = (scenario: SetupScenarioData): string => {
  if ("id" in scenario && scenario.id) return scenario.id;
  if ("scenario_id" in scenario && scenario.scenario_id) {
    return scenario.scenario_id;
  }
  return "";
};
