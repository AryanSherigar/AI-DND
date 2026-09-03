export type ActionMode = "say" | "do" | "story" | "see";

export interface TurnLogItem {
  id: string;
  turn_number: number;
  action_mode: ActionMode;
  action_text: string;
  narration_text: string;
  created_at: string;
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
}
