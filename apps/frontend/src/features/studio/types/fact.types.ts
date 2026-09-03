export interface FactCreate {
  subject_entity_id: string;
  predicate: string;
  object_entity_id?: string;
  object_literal?: string;
  valid_from?: string;
  when_active?: Record<string, unknown>;
  hidden?: boolean;
  superseded_fact_id?: string;
}

export interface FactUpdate {
  predicate?: string;
  object_entity_id?: string;
  object_literal?: string;
  valid_from?: string;
  when_active?: Record<string, unknown>;
  hidden?: boolean;
  superseded_fact_id?: string;
}

export interface FactResponse {
  fact_id: string;
  scenario_id: string;
  subject_entity_id: string;
  predicate: string;
  object_entity_id: string | null;
  object_literal: string | null;
  valid_from: string | null;
  when_active: Record<string, unknown> | null;
  hidden: boolean;
  superseded_fact_id: string | null;
}

export interface FactListResponse {
  items: FactResponse[];
}
