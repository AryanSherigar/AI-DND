import { SetupInputField } from "../stores/studio.store";

export type StateFieldType =
  | "string"
  | "number"
  | "boolean"
  | "enum"
  | "entity_ref"
  | "list"
  | "object"
  | "derived";

export interface StateFieldDefinition {
  type: StateFieldType;
  label?: string;
  initial?: unknown;
  min?: number;
  max?: number;
  entity_type?: string;
  fields?: Record<string, StateFieldDefinition>;
  item_type?: StateFieldType;
  formula?: string;
}

export interface SetupArchetype {
  id: string;
  name: string;
  values: Record<string, unknown>;
}

export type ScenarioMode = "newbie" | "master";

export type ScenarioStatus =
  | "draft"
  | "publishing"
  | "published"
  | "publish_failed"
  | "archived";

export type ScenarioComplexityTier = "newbie" | "intermediate" | "master";

export type ScenarioPlayerCountSupport = "solo" | "multiplayer" | "both";

export interface ScenarioRules {
  text?: string;
}

export interface ScenarioCreate {
  title: string;
  mode: ScenarioMode;
  complexity_tier: ScenarioComplexityTier;
  logline?: string;
  player_count_support?: ScenarioPlayerCountSupport;
  estimated_playtime?: string;
  cover_image_url?: string;
  content_tag?: string;
  genre_tags?: string[];
  narrator_persona?: string;
  world_data?: Record<string, unknown>;
  setup_schema?: SetupInputField[];
  state_schema?: Record<string, StateFieldDefinition>;
  end_conditions?: unknown[];
  checkpoints?: unknown[];
  rules?: ScenarioRules;
  opening_scene?: string;
  narration_font?: string;
  action_chips?: string[];
  setup_archetypes?: SetupArchetype[];
}

export interface ScenarioUpdate {
  title?: string;
  status?: "draft" | "archived";
  logline?: string;
  complexity_tier?: ScenarioComplexityTier;
  player_count_support?: ScenarioPlayerCountSupport;
  estimated_playtime?: string;
  cover_image_url?: string;
  content_tag?: string;
  genre_tags?: string[];
  narrator_persona?: string;
  world_data?: Record<string, unknown>;
  setup_schema?: SetupInputField[];
  state_schema?: Record<string, StateFieldDefinition>;
  end_conditions?: unknown[];
  checkpoints?: unknown[];
  rules?: ScenarioRules;
  opening_scene?: string;
  narration_font?: string;
  action_chips?: string[];
  setup_archetypes?: SetupArchetype[];
}

export interface ScenarioResponse {
  scenario_id: string;
  creator_id: string;
  creator_display_name: string | null;
  is_bookmarked: boolean;
  can_review: boolean;
  title: string;
  logline: string | null;
  mode: ScenarioMode;
  status: ScenarioStatus;
  genre_tags: string[];
  complexity_tier: ScenarioComplexityTier;
  player_count_support: ScenarioPlayerCountSupport;
  estimated_playtime: string | null;
  cover_image_url: string | null;
  content_tag: string | null;
  publish_error: string | null;
  published_at: string | null;
  play_count: number;
  rating_avg: string;
  narrator_persona: string | null;
  world_data: Record<string, unknown>;
  setup_schema: SetupInputField[];
  state_schema: Record<string, StateFieldDefinition>;
  end_conditions: unknown[];
  checkpoints: unknown[];
  rules: ScenarioRules;
  opening_scene: string | null;
  narration_font: string | null;
  action_chips: string[];
  setup_archetypes: SetupArchetype[];
  current_version: number;
  created_at: string;
  updated_at: string;
}
