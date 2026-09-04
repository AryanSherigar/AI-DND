import {
  PlaythroughResponse,
  ParticipantSummary,
} from "../api/playthroughs.api";
import { TurnLogListResponse } from "../api/turns.api";
import {
  CharacterSetupField,
  EntityAttributeSchemaField,
  EntityType,
  MasterEntity,
  Objective,
  PlayerStat,
  PlaythroughData,
  StoryCard,
  TurnLogItem,
} from "../types/play.types";
import { ScenarioMood } from "../types/audio.types";
import { buildChapterDeltaFromToolCalls } from "../utils/chapterDelta";

// Matches the shape features/studio/components/NewbieWizard/Step4Review.tsx
// writes into Scenario.world_data at creation time — see createDraft() there.
interface NewbieWorldData {
  worldLore?: string;
  openingPrompt?: string;
  singleLorePrompt?: string;
  initial_mood?: string;
  facts?: { id: number; text: string }[];
  storyCards?: { id: string; type: string; name: string; content: string }[];
}

interface SetupSchemaField {
  key: string;
  label: string;
}

interface MasterEntitySnapshot {
  entity_id: string;
  entity_type: EntityType;
  canonical_name: string;
  aliases: string[];
  description: string | null;
  attributes_schema: Record<string, EntityAttributeSchemaField>;
  obtainable: boolean | null;
}

interface EndConditionSnapshot {
  outcome_tag: "win" | "lose";
  outcome_title: string;
  outcome_text: string;
  is_secret: boolean;
}

interface StateSchemaFieldSnapshot {
  type: string;
  label?: string;
  fields?: Record<string, StateSchemaFieldSnapshot>;
}

interface CommonPlaythroughFields {
  playthrough_id: string;
  scenario_id: string;
  scenario_title: string;
  mode: "newbie" | "master";
  initial_mood?: ScenarioMood;
  creator_name: string;
  character_name: string;
  custom_fields: CharacterSetupField[];
  is_spectator: boolean;
  participant_id: string | null;
  can_act: boolean;
  next_actor_label: string | null;
}

/** Solo playthroughs always allow acting. Multiplayer cycles by turn_order_position. */
export function computeCanAct(
  participants: ParticipantSummary[],
  myParticipantId: string,
  turnCount: number,
): boolean {
  if (participants.length <= 1) return true;
  const ordered = [...participants].sort(
    (a, b) => a.turn_order_position - b.turn_order_position,
  );
  const expected = ordered[turnCount % ordered.length];
  return expected?.participant_id === myParticipantId;
}

/** Display label for the bottom bar's "Waiting for X..." state. */
export function computeNextActorLabel(
  participants: ParticipantSummary[],
  turnCount: number,
): string | null {
  if (participants.length <= 1) return null;
  const ordered = [...participants].sort(
    (a, b) => a.turn_order_position - b.turn_order_position,
  );
  const next = ordered[turnCount % ordered.length];
  return next ? `Player ${next.turn_order_position}` : null;
}

/** Maps submitted setup values to their creator-authored labels from setup_schema. */
function buildCustomFields(
  setupMap: Record<string, unknown>,
  setupSchema: SetupSchemaField[],
): CharacterSetupField[] {
  const labelByKey = new Map(
    setupSchema.map((field) => [field.key, field.label]),
  );
  return Object.entries(setupMap)
    .filter(([key]) => key !== "character_name")
    .map(([key, value]) => ({
      key,
      label: labelByKey.get(key) ?? key,
      value: Array.isArray(value) ? value.join(", ") : String(value ?? ""),
    }));
}

function titleCaseKey(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function buildCommonFields(
  serverPlaythrough: PlaythroughResponse,
  isSpectatorMode: boolean,
  mode: "newbie" | "master",
  initialMood: ScenarioMood | undefined,
  setupMap: Record<string, unknown>,
  setupSchema: SetupSchemaField[],
): CommonPlaythroughFields {
  const canAct = computeCanAct(
    serverPlaythrough.participants,
    serverPlaythrough.participant_id,
    serverPlaythrough.turn_count,
  );
  const nextActorLabel = computeNextActorLabel(
    serverPlaythrough.participants,
    serverPlaythrough.turn_count,
  );
  return {
    playthrough_id: serverPlaythrough.playthrough_id,
    scenario_id: serverPlaythrough.scenario_id,
    scenario_title: serverPlaythrough.scenario_title,
    mode,
    initial_mood: initialMood,
    creator_name: "Scenario Creator",
    character_name: (setupMap.character_name as string) || "Adventurer",
    custom_fields: buildCustomFields(setupMap, setupSchema),
    is_spectator: isSpectatorMode,
    participant_id: isSpectatorMode ? null : serverPlaythrough.participant_id,
    can_act: canAct,
    next_actor_label: nextActorLabel,
  };
}

export function buildNewbiePlaythroughData(
  serverPlaythrough: PlaythroughResponse,
  turnsData: TurnLogListResponse | undefined,
  isSpectatorMode: boolean,
): PlaythroughData {
  const setupMap = (serverPlaythrough.state?.setup || {}) as Record<
    string,
    unknown
  >;
  const snapshot = serverPlaythrough.scenario_snapshot || {};
  const worldData = (snapshot.world_data ?? {}) as NewbieWorldData;
  const setupSchema = (snapshot.setup_schema ?? []) as SetupSchemaField[];

  const turns: TurnLogItem[] = (turnsData?.items ?? []).map((turn) => ({
    id: turn.turn_id,
    turn_number: turn.turn_number,
    action_mode: "do",
    action_text: turn.action_text,
    narration_text: turn.narration_text ?? "",
    created_at: turn.created_at,
  }));

  return {
    ...buildCommonFields(
      serverPlaythrough,
      isSpectatorMode,
      "newbie",
      (worldData.initial_mood as ScenarioMood) || undefined,
      setupMap,
      setupSchema,
    ),
    opening_premise:
      worldData.openingPrompt ||
      worldData.singleLorePrompt ||
      "Your chronicle begins...",
    world_lore:
      worldData.worldLore ||
      worldData.singleLorePrompt ||
      "No world lore recorded.",
    key_facts: (worldData.facts ?? []).map((fact) => fact.text),
    story_cards: (worldData.storyCards ?? []).map((card): StoryCard => ({
      id: card.id,
      title: card.name,
      category: card.type,
      content: card.content,
    })),
    turns,
    entities: [],
    active_conditions: [],
    objectives: [],
    player_stats: [],
    player_inventory: [],
  };
}

function buildMasterEntities(
  snapshot: Record<string, unknown>,
  state: Record<string, unknown>,
): MasterEntity[] {
  const entitiesSnapshot = (snapshot.entities ?? []) as MasterEntitySnapshot[];
  const liveStates = (state.entities ?? {}) as Record<
    string,
    Record<string, unknown>
  >;
  return entitiesSnapshot.map((entity) => ({
    ...entity,
    attributes: liveStates[entity.entity_id] ?? {},
  }));
}

function buildPlayerStats(
  playerFields: Record<string, StateSchemaFieldSnapshot>,
  playerState: Record<string, unknown>,
): PlayerStat[] {
  return Object.entries(playerFields)
    .filter(([, field]) => field.type !== "entity_ref" && field.type !== "list")
    .map(([key, field]) => ({
      key,
      label: field.label ?? titleCaseKey(key),
      value: playerState[key],
    }));
}

function buildPlayerInventory(
  playerFields: Record<string, StateSchemaFieldSnapshot>,
  playerState: Record<string, unknown>,
  entities: MasterEntity[],
): MasterEntity[] {
  const entityById = new Map(entities.map((e) => [e.entity_id, e]));
  const inventoryIds = Object.entries(playerFields)
    .filter(([, field]) => field.type === "list")
    .flatMap(([key]) => (playerState[key] as string[] | undefined) ?? []);
  return inventoryIds
    .map((id) => entityById.get(id))
    .filter((e): e is MasterEntity => e !== undefined);
}

function buildObjectives(snapshot: Record<string, unknown>): Objective[] {
  const endConditions = (snapshot.end_conditions ??
    []) as EndConditionSnapshot[];
  return endConditions
    .filter((ec) => !ec.is_secret)
    .map((ec) => ({
      outcome_title: ec.outcome_title,
      outcome_tag: ec.outcome_tag,
      outcome_text: ec.outcome_text,
    }));
}

export function buildMasterPlaythroughData(
  serverPlaythrough: PlaythroughResponse,
  turnsData: TurnLogListResponse | undefined,
  isSpectatorMode: boolean,
): PlaythroughData {
  const setupMap = (serverPlaythrough.state?.setup || {}) as Record<
    string,
    unknown
  >;
  const snapshot = serverPlaythrough.scenario_snapshot || {};
  const setupSchema = (snapshot.setup_schema ?? []) as SetupSchemaField[];
  const state = serverPlaythrough.state || {};

  const entities = buildMasterEntities(snapshot, state);
  const stateSchema = (snapshot.state_schema ?? {}) as Record<
    string,
    StateSchemaFieldSnapshot
  >;
  const playerFields = stateSchema.player?.fields ?? {};
  const playerState = (state.player ?? {}) as Record<string, unknown>;

  const turns: TurnLogItem[] = (turnsData?.items ?? []).map((turn) => ({
    id: turn.turn_id,
    turn_number: turn.turn_number,
    action_mode: "do",
    action_text: turn.action_text,
    narration_text: turn.narration_text ?? "",
    created_at: turn.created_at,
    chapter_delta: buildChapterDeltaFromToolCalls(turn.tool_calls, entities),
  }));

  return {
    ...buildCommonFields(
      serverPlaythrough,
      isSpectatorMode,
      "master",
      undefined,
      setupMap,
      setupSchema,
    ),
    opening_premise: "Your chronicle begins...",
    world_lore: "",
    key_facts: [],
    story_cards: [],
    turns,
    entities,
    active_conditions: serverPlaythrough.active_conditions ?? [],
    objectives: buildObjectives(snapshot),
    player_stats: buildPlayerStats(playerFields, playerState),
    player_inventory: buildPlayerInventory(playerFields, playerState, entities),
  };
}
