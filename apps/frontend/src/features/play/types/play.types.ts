import { ScenarioMood } from "./audio.types";

export type ActionMode = "say" | "do" | "story" | "see";

export type EBookTheme = "dark-velvet" | "antique-sepia";

export type EntityType =
  "character" | "location" | "item" | "faction" | "organization";

export interface EntityAttributeSchemaField {
  type: "string" | "number" | "boolean" | "enum";
  label?: string;
}

export interface MasterEntity {
  entity_id: string;
  entity_type: EntityType;
  canonical_name: string;
  aliases: string[];
  description: string | null;
  attributes_schema: Record<string, EntityAttributeSchemaField>;
  obtainable: boolean | null;
  // Live values, resolved from PlaythroughResponse.state.entities[entity_id].
  attributes: Record<string, unknown>;
}

export interface Objective {
  outcome_title: string;
  outcome_tag: "win" | "lose";
  outcome_text: string;
}

export interface PlayerStat {
  key: string;
  label: string;
  value: unknown;
}

export interface StatChange {
  path: string;
  label: string;
  before?: string | number | boolean | null;
  after?: string | number | boolean | null;
  delta?: number | null;
}

export interface InventoryChange {
  path: string;
  entity_id: string;
  entity_display_name: string;
}

export interface DiceRoll {
  expression: string;
  sides: number;
  modifier: number;
  roll: number;
  total: number;
}

export interface ChapterDelta {
  stat_changes: StatChange[];
  inventory_changes: InventoryChange[];
  dice_rolls: DiceRoll[];
}

export interface EntityHighlightItem {
  id: string;
  name: string;
  category: string;
  summary: string;
  // Live attribute label/value pairs — present only for master entities.
  attributes?: { label: string; value: string }[];
}

export interface TurnLogItem {
  id: string;
  turn_number: number;
  action_mode: ActionMode;
  action_text: string;
  narration_text: string;
  created_at: string;
  // Populated for master mode: live via SSE, or reconstructed from
  // tool_calls on reload — see utils/chapterDelta.ts.
  chapter_delta?: ChapterDelta;
}

export interface CharacterSetupField {
  key: string;
  label: string;
  value: string;
}

export interface StoryCard {
  id: string;
  title: string;
  category: string;
  content: string;
}

export interface PlaythroughData {
  playthrough_id: string;
  scenario_id: string;
  scenario_title: string;
  mode: "newbie" | "master";
  initial_mood?: ScenarioMood;
  creator_name: string;
  cover_image_url?: string;
  opening_premise: string;
  world_lore: string;
  key_facts: string[];
  story_cards: StoryCard[];
  character_name: string;
  custom_fields: CharacterSetupField[];
  turns: TurnLogItem[];
  is_spectator: boolean;
  // The requesting user's own participant_id — required by POST /v1/turn.
  // Absent for spectators, who never submit turns.
  participant_id: string | null;
  // Multiplayer turn-order gate: false when it's another participant's turn.
  // Always true for solo playthroughs and irrelevant for spectators.
  can_act: boolean;
  // Display name of whoever acts next, for the "Waiting for X..." bottom-bar
  // state when !can_act. Null for solo playthroughs (can_act is always true).
  next_actor_label: string | null;
  // Master-mode-only fields — [] for newbie.
  entities: MasterEntity[];
  active_conditions: string[];
  objectives: Objective[];
  player_stats: PlayerStat[];
  player_inventory: MasterEntity[];
}
