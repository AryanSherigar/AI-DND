import { useRef } from "react";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";
import { useEntities } from "./useEntities";
import { useFacts } from "./useFacts";
import { useScenario } from "./useScenario";
import { ActionBlock } from "../types/assistant.types";
import { AttributeFieldSchema, EntityCreate } from "../types/entity.types";
import { FactCreate } from "../types/fact.types";
import { StateFieldDefinition } from "../types/scenario.types";

interface RawFactPayload {
  subject_entity_id?: string;
  subject_ref?: string;
  predicate: string;
  object_entity_id?: string;
  object_ref?: string;
  object_literal?: string;
  hidden?: boolean;
}

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const isResolvedEntityId = (id?: string): id is string =>
  Boolean(id && UUID_PATTERN.test(id));

const SCENARIO_TEXT_FIELD_BY_TARGET: Record<string, string> = {
  title: "title",
  logline: "logline",
  opening_prompt: "opening_scene",
};

const ATTRIBUTE_TYPE_KEYWORDS = new Set([
  "string",
  "number",
  "boolean",
  "enum",
]);

/**
 * The AI is inconsistent about attributes_schema's shape — sometimes it sends
 * the intended {type, initial} object, sometimes just a type name ("hunger":
 * "number"), sometimes a bare initial value ("age": 34). All three express
 * the same intent, so infer a valid AttributeFieldSchema from whatever shows
 * up rather than rejecting a suggestion whose meaning is perfectly clear.
 */
const normalizeAttributeField = (value: unknown): AttributeFieldSchema => {
  if (value && typeof value === "object" && "type" in value) {
    const declaredType = (value as { type: unknown }).type;
    if (
      typeof declaredType === "string" &&
      ATTRIBUTE_TYPE_KEYWORDS.has(declaredType)
    ) {
      return value as AttributeFieldSchema;
    }
  }
  if (typeof value === "string" && ATTRIBUTE_TYPE_KEYWORDS.has(value)) {
    return { type: value as AttributeFieldSchema["type"] };
  }
  if (typeof value === "number") return { type: "number", initial: value };
  if (typeof value === "boolean") return { type: "boolean", initial: value };
  if (typeof value === "string") return { type: "string", initial: value };
  return { type: "string" };
};

const normalizeAttributesSchema = (
  raw: unknown,
): Record<string, AttributeFieldSchema> => {
  if (!raw || typeof raw !== "object") return {};
  return Object.fromEntries(
    Object.entries(raw as Record<string, unknown>).map(([key, value]) => [
      key,
      normalizeAttributeField(value),
    ]),
  );
};

/** Every top-level {...} object found in `text`, in order, ignoring nesting. */
const extractJsonObjects = (text: string): Record<string, unknown>[] => {
  const objects: Record<string, unknown>[] = [];
  let depth = 0;
  let start = -1;
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (char === "{") {
      if (depth === 0) start = i;
      depth++;
    } else if (char === "}") {
      depth--;
      if (depth === 0 && start !== -1) {
        try {
          const parsed = JSON.parse(text.slice(start, i + 1));
          if (parsed && typeof parsed === "object") objects.push(parsed);
        } catch {
          // not valid JSON on its own — skip it
        }
        start = -1;
      }
    }
  }
  return objects;
};

/**
 * Entity/state_field content should be one JSON object, but the model
 * sometimes splits it into several consecutive objects in the same block
 * (e.g. a bare {"temp_id": "..."} followed by the actual entity fields).
 * Parse the happy path first; if that fails, merge every top-level object
 * found in the block instead of rejecting a suggestion whose pieces are all
 * individually well-formed.
 */
const parseBlockJson = (content: string): Record<string, unknown> | null => {
  try {
    const parsed = JSON.parse(content);
    if (parsed && typeof parsed === "object")
      return parsed as Record<string, unknown>;
  } catch {
    // fall through to the multi-object merge below
  }
  const objects = extractJsonObjects(content);
  return objects.length > 0 ? Object.assign({}, ...objects) : null;
};

/**
 * Applies AI-suggested master-mode action blocks by calling the same
 * core-api mutations the manual Entity/Fact/Setup forms already use.
 * Kept separate from AIChatSidebar so each apply path stays a small,
 * single-responsibility function.
 */
export const useMasterActionApplier = (
  scenarioId: string | null,
  onError: (message: string) => void,
) => {
  const { createEntity, deleteEntity } = useEntities(scenarioId);
  const { createFact, deleteFact } = useFacts(scenarioId);
  const { scenario, updateScenario } = useScenario(scenarioId);
  const tempIdMapRef = useRef<Map<string, string>>(new Map());

  const resolveRef = (ref?: string): string | undefined =>
    ref ? (tempIdMapRef.current.get(ref) ?? ref) : undefined;

  const applyEntityBlock = (block: ActionBlock): Promise<void> =>
    new Promise((resolve) => {
      const raw = parseBlockJson(block.content);
      if (!raw) {
        onError("Couldn't read the entity suggestion — invalid data.");
        resolve();
        return;
      }
      const { temp_id: contentTempId, op: _op, ...rest } = raw;
      const tempId =
        (contentTempId as string | undefined) ?? block.metadata?.temp_id;
      const payload = rest as unknown as EntityCreate;
      if (payload.attributes_schema) {
        payload.attributes_schema = normalizeAttributesSchema(
          payload.attributes_schema,
        );
      }
      createEntity(payload, {
        onSuccess: (created) => {
          if (tempId) tempIdMapRef.current.set(tempId, created.entity_id);
          resolve();
        },
        onError: (err) => {
          onError(
            extractErrorMessage(
              err,
              `Couldn't create entity "${payload.canonical_name}".`,
            ),
          );
          resolve();
        },
      });
    });

  const applyFactBlock = (block: ActionBlock): Promise<void> =>
    new Promise((resolve) => {
      let raw: RawFactPayload;
      try {
        raw = JSON.parse(block.content);
      } catch {
        onError("Couldn't read the fact suggestion — invalid data.");
        resolve();
        return;
      }
      const subjectRef = raw.subject_entity_id ?? raw.subject_ref;
      const subjectId = resolveRef(subjectRef);
      if (!isResolvedEntityId(subjectId)) {
        onError(
          `Couldn't create fact "${raw.predicate}" — its subject entity ` +
            `"${subjectRef ?? "(missing)"}" hasn't been created yet. Apply that ` +
            "entity's suggestion first.",
        );
        resolve();
        return;
      }
      const objectRef = raw.object_literal
        ? undefined
        : (raw.object_entity_id ?? raw.object_ref);
      const objectId = objectRef ? resolveRef(objectRef) : undefined;
      if (objectRef && !isResolvedEntityId(objectId)) {
        onError(
          `Couldn't create fact "${raw.predicate}" — its object entity ` +
            `"${objectRef}" hasn't been created yet. Apply that entity's ` +
            "suggestion first.",
        );
        resolve();
        return;
      }
      const payload: FactCreate = {
        subject_entity_id: subjectId,
        predicate: raw.predicate,
        object_entity_id: objectId,
        object_literal: raw.object_literal,
        hidden: raw.hidden,
      };
      createFact(payload, {
        onSuccess: () => resolve(),
        onError: (err) => {
          onError(
            extractErrorMessage(
              err,
              `Couldn't create fact "${raw.predicate}".`,
            ),
          );
          resolve();
        },
      });
    });

  const applyStateFieldBlock = (block: ActionBlock): Promise<void> =>
    new Promise((resolve) => {
      const raw = parseBlockJson(block.content);
      if (!raw) {
        onError("Couldn't read the tracked value suggestion — invalid data.");
        resolve();
        return;
      }
      const { key: contentKey, ...definition } = raw;
      const key = (contentKey as string | undefined) ?? block.metadata?.key;
      if (!key) {
        onError("Couldn't add the tracked value — missing field key.");
        resolve();
        return;
      }
      const merged = {
        ...(scenario?.state_schema || {}),
        [key]: definition as unknown as StateFieldDefinition,
      };
      updateScenario(
        { state_schema: merged },
        {
          onSuccess: () => resolve(),
          onError: (err) => {
            onError(
              extractErrorMessage(err, `Couldn't add tracked value "${key}".`),
            );
            resolve();
          },
        },
      );
    });

  const applyScenarioTextBlock = (block: ActionBlock): Promise<void> =>
    new Promise((resolve) => {
      // "instructions" maps to House Rules (rules.text) — the only free-text
      // narrator-guidance field master mode actually has an editor for.
      const isRules = block.target === "instructions";
      const field = isRules
        ? "rules"
        : SCENARIO_TEXT_FIELD_BY_TARGET[block.target];
      if (!field) {
        resolve();
        return;
      }
      const payload = isRules ? { text: block.content } : block.content;
      updateScenario(
        { [field]: payload },
        {
          onSuccess: () => resolve(),
          onError: (err) => {
            onError(extractErrorMessage(err, `Couldn't update ${field}.`));
            resolve();
          },
        },
      );
    });

  const applyBlock = (block: ActionBlock): Promise<void> => {
    switch (block.target) {
      case "entity":
        return applyEntityBlock(block);
      case "fact":
        return applyFactBlock(block);
      case "state_field":
        return applyStateFieldBlock(block);
      case "title":
      case "logline":
      case "opening_prompt":
      case "instructions":
        return applyScenarioTextBlock(block);
      default:
        return Promise.resolve();
    }
  };

  const applyBatch = async (blocks: ActionBlock[]): Promise<void> => {
    const entityBlocks = blocks.filter((b) => b.target === "entity");
    const remainingBlocks = blocks.filter((b) => b.target !== "entity");
    for (const block of entityBlocks) {
      await applyBlock(block);
    }
    for (const block of remainingBlocks) {
      await applyBlock(block);
    }
  };

  const applyDestructive = (block: ActionBlock): Promise<void> =>
    new Promise((resolve) => {
      let payload: { entity_id?: string; fact_id?: string };
      try {
        payload = JSON.parse(block.content);
      } catch {
        onError("Couldn't read the delete suggestion — invalid data.");
        resolve();
        return;
      }
      const settle = (err?: unknown) => {
        if (err) {
          onError(
            extractErrorMessage(err, "Couldn't delete the requested item."),
          );
        }
        resolve();
      };
      if (block.target === "entity" && payload.entity_id) {
        deleteEntity(payload.entity_id, {
          onSuccess: () => settle(),
          onError: settle,
        });
      } else if (block.target === "fact" && payload.fact_id) {
        deleteFact(payload.fact_id, {
          onSuccess: () => settle(),
          onError: settle,
        });
      } else {
        onError("Couldn't determine what to delete.");
        resolve();
      }
    });

  return { applyBlock, applyBatch, applyDestructive };
};
