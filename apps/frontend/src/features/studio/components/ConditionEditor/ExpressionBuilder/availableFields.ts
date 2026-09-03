import {
  StateFieldDefinition,
  StateFieldType,
} from "../../../types/scenario.types";
import {
  AttributeFieldType,
  EntityResponse,
} from "../../../types/entity.types";
import { AvailableField } from "./ExpressionBuilder.types";

const STATE_TYPE_TO_FIELD_TYPE: Partial<
  Record<StateFieldType, AvailableField["type"]>
> = {
  string: "string",
  number: "number",
  boolean: "boolean",
  enum: "enum",
  entity_ref: "entity_ref",
};

const slugifyCanonicalName = (canonicalName: string): string =>
  canonicalName.trim().toLowerCase().replace(/\s+/g, "_");

const buildLabel = (
  definition: StateFieldDefinition,
  fallbackKey: string,
): string => definition.label ?? fallbackKey;

const buildStateFields = (
  stateSchema: Record<string, StateFieldDefinition>,
  pathPrefix: string,
): AvailableField[] => {
  const fields: AvailableField[] = [];

  for (const [key, definition] of Object.entries(stateSchema)) {
    const path = pathPrefix ? `${pathPrefix}.${key}` : key;

    if (definition.type === "object") {
      fields.push(...buildStateFields(definition.fields ?? {}, path));
      continue;
    }

    if (definition.type === "list") {
      continue;
    }

    if (definition.type === "derived") {
      // NOTE: derived fields carry no declared value type of their own, so we
      // default to "string" — the ExpressionBuilder's ValueInput still allows
      // free-form comparison values regardless of this default.
      fields.push({ path, label: buildLabel(definition, key), type: "string" });
      continue;
    }

    fields.push({
      path,
      label: buildLabel(definition, key),
      type: STATE_TYPE_TO_FIELD_TYPE[definition.type] ?? "string",
    });
  }

  return fields;
};

const ATTRIBUTE_TYPE_TO_FIELD_TYPE: Record<
  AttributeFieldType,
  AvailableField["type"]
> = {
  string: "string",
  number: "number",
  boolean: "boolean",
  enum: "enum",
};

const buildEntityFields = (entities: EntityResponse[]): AvailableField[] => {
  const fields: AvailableField[] = [];

  for (const entity of entities) {
    const entitySlug = slugifyCanonicalName(entity.canonical_name);

    for (const [attributeKey, attributeSchema] of Object.entries(
      entity.attributes_schema,
    )) {
      fields.push({
        path: `${entitySlug}.${attributeKey}`,
        label: attributeSchema.label ?? attributeKey,
        type: ATTRIBUTE_TYPE_TO_FIELD_TYPE[attributeSchema.type] ?? "string",
      });
    }
  }

  return fields;
};

export const buildAvailableFields = (
  stateSchema: Record<string, StateFieldDefinition>,
  entities: EntityResponse[],
): AvailableField[] => [
  ...buildStateFields(stateSchema, ""),
  ...buildEntityFields(entities),
];
