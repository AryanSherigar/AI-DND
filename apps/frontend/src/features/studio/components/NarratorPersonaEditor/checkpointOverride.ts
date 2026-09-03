import { CheckpointPersonaOverride } from "./NarratorPersonaEditor.types";

const readStringField = (
  record: Record<string, unknown>,
  key: string,
): string => {
  const value = record[key];
  return typeof value === "string" ? value : "";
};

export const toCheckpointOverride = (
  raw: unknown,
): CheckpointPersonaOverride => {
  const record = (raw ?? {}) as Record<string, unknown>;
  return {
    checkpoint_id: readStringField(record, "checkpoint_id"),
    trigger_description: readStringField(record, "trigger_description"),
    persona_override: readStringField(record, "persona_override"),
  };
};

export const createCheckpointOverride = (): CheckpointPersonaOverride => ({
  checkpoint_id: crypto.randomUUID(),
  trigger_description: "",
  persona_override: "",
});
