export type ActionTarget =
  | "title"
  | "logline"
  | "lore"
  | "opening_prompt"
  | "conflict"
  | "story_card"
  | "style"
  | "instructions"
  | "entity"
  | "fact"
  | "state_field"
  | "condition"
  | "invariant"
  | "end_condition"
  | "minigame";

export const MASTER_STRUCTURED_TARGETS: ActionTarget[] = [
  "entity",
  "fact",
  "state_field",
];

export const MASTER_EXPRESSION_TARGETS: ActionTarget[] = [
  "condition",
  "invariant",
  "end_condition",
];

export interface BlockValidation {
  index: number;
  errors: string[];
}

export interface ActionBlock {
  target: ActionTarget;
  metadata?: {
    type?: string;
    name?: string;
    op?: "create" | "delete";
    temp_id?: string;
    key?: string;
  };
  content: string;
}

/**
 * Master-mode entity/fact/state_field blocks carry temp_id/key/op inside
 * their own JSON content rather than as fence-line metadata (the model
 * doesn't reliably format that convention), so "is this a delete" has to
 * check both places — metadata for older-style blocks, content for the
 * current one.
 */
export const isDeleteActionBlock = (block: ActionBlock): boolean => {
  if (block.metadata?.op === "delete") return true;
  try {
    const parsed = JSON.parse(block.content);
    return Boolean(
      parsed && typeof parsed === "object" && parsed.op === "delete",
    );
  } catch {
    return false;
  }
};

export interface AssistantMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

export interface ConflictModalState {
  isOpen: boolean;
  target: ActionTarget;
  targetLabel: string;
  existingValue: string;
  newValue: string;
  metadata?: {
    type?: string;
    name?: string;
  };
}

export interface DestructiveConfirmState {
  isOpen: boolean;
  block: ActionBlock | null;
  description: string;
}

export interface AssistantMasterContextEntity {
  entity_id: string;
  entity_type: string;
  canonical_name: string;
  description?: string;
  attributes_schema?: Record<string, unknown>;
}

export interface AssistantMasterContextFact {
  fact_id: string;
  subject_entity_id: string;
  predicate: string;
  object_entity_id?: string | null;
  object_literal?: string | null;
}

export interface AssistantMasterContextCondition {
  condition_id: string;
  label: string;
}

export interface AssistantMasterContextInvariant {
  invariant_id: string;
  label: string;
}

export interface AssistantMasterContextEndCondition {
  end_condition_id: string;
  outcome_tag: string;
  outcome_title: string;
}

export interface AssistantMasterContext {
  title: string;
  logline: string;
  narrator_persona: string;
  opening_scene: string;
  state_schema: Record<string, unknown>;
  entities: AssistantMasterContextEntity[];
  facts: AssistantMasterContextFact[];
  conditions: AssistantMasterContextCondition[];
  invariants: AssistantMasterContextInvariant[];
  end_conditions: AssistantMasterContextEndCondition[];
  active_tab: string;
}

export const ACTION_TARGET_LABELS: Record<ActionTarget, string> = {
  title: "Scenario Title",
  logline: "Logline / Summary",
  lore: "World Lore",
  opening_prompt: "Opening Scene Hook",
  conflict: "Main Conflict / Goal",
  story_card: "Story Card",
  style: "Narrative Style & Vibe",
  instructions: "AI Narrator Guardrails",
  entity: "Entity",
  fact: "Fact",
  state_field: "Tracked Value",
  condition: "Active Rule",
  invariant: "Always-True Rule",
  end_condition: "Win/Lose Condition",
  minigame: "Minigame",
};
