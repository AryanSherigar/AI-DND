export interface InvariantCreate {
  label: string;
  invariant_expression: Record<string, unknown>;
  applies_to: string;
  narrator_text: string;
}

export interface InvariantUpdate {
  label?: string;
  invariant_expression?: Record<string, unknown>;
  applies_to?: string;
  narrator_text?: string;
}

export interface InvariantResponse {
  invariant_id: string;
  scenario_id: string;
  label: string;
  invariant_expression: Record<string, unknown>;
  applies_to: string;
  narrator_text: string;
}

export interface InvariantListResponse {
  items: InvariantResponse[];
}
