// Master-mode Maps shapes, shared between studio/ (authoring) and play/
// (viewing) — features never import from each other, so this shape lives in
// shared/ per CLAUDE.md. See docs/specs/master-mode-maps.spec.md.

export interface ScenarioMap {
  map_id: string;
  scenario_id: string;
  name: string;
  image_url: string | null;
  display_order: number;
}

export interface MapPin {
  pin_id: string;
  map_id: string;
  scenario_id: string;
  entity_id: string;
  x: number; // 0-1, image-relative
  y: number;
  is_start_location: boolean;
}

export interface MapConnection {
  connection_id: string;
  scenario_id: string;
  entity_id_a: string;
  entity_id_b: string;
  label: string | null;
}
