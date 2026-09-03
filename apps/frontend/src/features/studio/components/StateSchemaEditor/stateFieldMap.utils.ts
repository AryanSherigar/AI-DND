import { StateFieldDefinition } from "../../types/scenario.types";

const NEW_FIELD_PREFIX = "field_";

export const buildUnusedFieldKey = (
  fields: Record<string, StateFieldDefinition>,
): string => {
  let index = Object.keys(fields).length + 1;
  let candidate = `${NEW_FIELD_PREFIX}${index}`;
  while (fields[candidate]) {
    index += 1;
    candidate = `${NEW_FIELD_PREFIX}${index}`;
  }
  return candidate;
};

export const renameFieldKey = (
  fields: Record<string, StateFieldDefinition>,
  oldKey: string,
  newKey: string,
): Record<string, StateFieldDefinition> => {
  const trimmedKey = newKey.trim();
  if (!trimmedKey || trimmedKey === oldKey || fields[trimmedKey]) {
    return fields;
  }
  const next: Record<string, StateFieldDefinition> = {};
  Object.entries(fields).forEach(([entryKey, schema]) => {
    next[entryKey === oldKey ? trimmedKey : entryKey] = schema;
  });
  return next;
};

export const removeFieldKey = (
  fields: Record<string, StateFieldDefinition>,
  key: string,
): Record<string, StateFieldDefinition> => {
  const next = { ...fields };
  delete next[key];
  return next;
};

export const patchField = (
  fields: Record<string, StateFieldDefinition>,
  key: string,
  patch: Partial<StateFieldDefinition>,
): Record<string, StateFieldDefinition> => ({
  ...fields,
  [key]: { ...fields[key], ...patch },
});

export const buildDefaultFieldDefinition = (): StateFieldDefinition => ({
  type: "string",
  initial: "",
});
