export const OUTCOME_TAGS = ["win", "lose"] as const;

export type OutcomeTag = (typeof OUTCOME_TAGS)[number];

export interface EndConditionCreate {
  condition_expression?: Record<string, unknown>;
  outcome_tag: OutcomeTag;
  outcome_title: string;
  outcome_text: string;
  is_secret?: boolean;
  priority?: number;
}

export interface EndConditionUpdate {
  condition_expression?: Record<string, unknown>;
  outcome_tag?: OutcomeTag;
  outcome_title?: string;
  outcome_text?: string;
  is_secret?: boolean;
  priority?: number;
}

export interface EndConditionResponse {
  end_condition_id: string;
  scenario_id: string;
  condition_expression: Record<string, unknown>;
  outcome_tag: OutcomeTag;
  outcome_title: string;
  outcome_text: string;
  is_secret: boolean;
  priority: number;
}

export interface EndConditionListResponse {
  items: EndConditionResponse[];
}
