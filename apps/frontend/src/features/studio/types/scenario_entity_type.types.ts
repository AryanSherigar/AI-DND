import { AttributeFieldSchema } from "./entity.types";

export interface ScenarioEntityTypeCreate {
  type_key: string;
  display_label: string;
  attributes_schema?: Record<string, AttributeFieldSchema>;
}

export interface ScenarioEntityTypeUpdate {
  display_label?: string;
  attributes_schema?: Record<string, AttributeFieldSchema>;
}

export interface ScenarioEntityTypeResponse {
  scenario_entity_type_id: string;
  scenario_id: string;
  type_key: string;
  display_label: string;
  attributes_schema: Record<string, AttributeFieldSchema>;
}

export interface ScenarioEntityTypeListResponse {
  items: ScenarioEntityTypeResponse[];
}
