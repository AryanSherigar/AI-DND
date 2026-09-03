export type StateMutationOp = "set" | "increment" | "decrement";

export interface StateMutation {
  path: string;
  op: StateMutationOp;
  value: unknown;
}

export interface ConditionCreate {
  label: string;
  condition_expression?: Record<string, unknown>;
  narrator_instruction: string;
  metadata?: Record<string, unknown>;
  state_mutation?: StateMutation;
}

export interface ConditionUpdate {
  label?: string;
  condition_expression?: Record<string, unknown>;
  narrator_instruction?: string;
  metadata?: Record<string, unknown>;
  state_mutation?: StateMutation;
}

export interface ConditionResponse {
  condition_id: string;
  scenario_id: string;
  label: string;
  condition_expression: Record<string, unknown>;
  condition_version: string;
  narrator_instruction: string;
  metadata: Record<string, unknown>;
  state_mutation: StateMutation | null;
}

export interface ConditionListResponse {
  items: ConditionResponse[];
}
