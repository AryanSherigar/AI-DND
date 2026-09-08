// Studio-side wire shapes for scenario_minigames. The play-time payload
// shapes (MinigameEventPayload/MinigameResultPayload) and the mutation
// shape live in shared/types/minigame.types.ts — re-exported here, never
// redefined, so studio/ and play/ never duplicate the same shape.
import type {
  DodgeConfigShape,
  MinigameType,
  OutcomeMode,
  StateMutation,
  TieredOutcomeRange,
} from "@/shared/types/minigame.types";

export { DEFAULT_DODGE_CONFIG } from "@/shared/types/minigame.types";

export type {
  DodgeConfigShape,
  MinigameOutcomeTag,
  MinigameType,
  OutcomeMode,
  StateMutation,
  StateMutationOp,
  TieredOutcomeRange,
} from "@/shared/types/minigame.types";

export interface MinigameCreate {
  label: string;
  minigame_type: MinigameType;
  trigger_condition_expression?: Record<string, unknown>;
  priority?: number;
  outcome_mode: OutcomeMode;
  win_mutation?: StateMutation | null;
  lose_mutation?: StateMutation | null;
  tiered_outcomes?: TieredOutcomeRange[];
  timeout_mutation?: StateMutation | null;
  narrator_instruction_template?: string | null;
  dodge_config?: DodgeConfigShape | null;
  replit_embed_url?: string | null;
}

export interface MinigameUpdate {
  label?: string;
  trigger_condition_expression?: Record<string, unknown>;
  priority?: number;
  outcome_mode?: OutcomeMode;
  win_mutation?: StateMutation | null;
  lose_mutation?: StateMutation | null;
  tiered_outcomes?: TieredOutcomeRange[];
  timeout_mutation?: StateMutation | null;
  narrator_instruction_template?: string | null;
  dodge_config?: DodgeConfigShape | null;
  replit_embed_url?: string | null;
}

export interface MinigameResponse {
  minigame_id: string;
  scenario_id: string;
  label: string;
  minigame_type: MinigameType;
  trigger_condition_expression: Record<string, unknown>;
  priority: number;
  outcome_mode: OutcomeMode;
  win_mutation: StateMutation | null;
  lose_mutation: StateMutation | null;
  tiered_outcomes: TieredOutcomeRange[];
  timeout_mutation: StateMutation | null;
  narrator_instruction_template: string | null;
  dodge_config: DodgeConfigShape | null;
  replit_embed_url: string | null;
}

export interface MinigameListResponse {
  items: MinigameResponse[];
}
