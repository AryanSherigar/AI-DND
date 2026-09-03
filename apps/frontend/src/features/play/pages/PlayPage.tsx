import { useEffect } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { PlayScreen } from "../components/PlayScreen/PlayScreen";
import { usePlayStore } from "../stores/play.store";
import { usePlaythrough } from "../hooks/usePlaythrough";
import { usePlaythroughTurns } from "../hooks/useTurns";
import { useNotifications } from "../hooks/useNotifications";
import {
  CharacterSetupField,
  StoryCard,
  TurnLogItem,
  PlaythroughData,
} from "../types/play.types";
import { ParticipantSummary } from "../api/playthroughs.api";

// Matches the shape features/studio/components/NewbieWizard/Step4Review.tsx
// writes into Scenario.world_data at creation time — see createDraft() there.
interface NewbieWorldData {
  worldLore?: string;
  openingPrompt?: string;
  singleLorePrompt?: string;
  facts?: { id: number; text: string }[];
  storyCards?: { id: string; type: string; name: string; content: string }[];
}

interface SetupSchemaField {
  key: string;
  label: string;
}

/** Maps submitted setup values to their creator-authored labels from setup_schema. */
function buildCustomFields(
  setupMap: Record<string, unknown>,
  setupSchema: SetupSchemaField[],
): CharacterSetupField[] {
  const labelByKey = new Map(setupSchema.map((field) => [field.key, field.label]));
  return Object.entries(setupMap)
    .filter(([key]) => key !== "character_name")
    .map(([key, value]) => ({
      key,
      label: labelByKey.get(key) ?? key,
      value: Array.isArray(value) ? value.join(", ") : String(value ?? ""),
    }));
}

export function PlayPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const setPlaythrough = usePlayStore((s) => s.setPlaythrough);
  const queryClient = useQueryClient();

  const {
    data: serverPlaythrough,
    isLoading,
    isError,
  } = usePlaythrough(id);
  const { data: turnsData } = usePlaythroughTurns(id);

  const isSpectatorMode = searchParams.get("mode") === "spectate";
  const isMultiplayer = (serverPlaythrough?.participants.length ?? 0) > 1;

  const { isMyTurnSignal, acknowledgeMyTurn } = useNotifications(
    id ?? null,
    serverPlaythrough?.participant_id ?? null,
    isMultiplayer && !isSpectatorMode,
  );

  useEffect(() => {
    if (!isMyTurnSignal || !id) return;
    void queryClient.invalidateQueries({ queryKey: ["playthrough", id] });
    acknowledgeMyTurn();
  }, [isMyTurnSignal, id, queryClient, acknowledgeMyTurn]);

  useEffect(() => {
    if (!serverPlaythrough) return;

    const setupMap = (serverPlaythrough.state?.setup || {}) as Record<
      string,
      unknown
    >;

    const snapshot = serverPlaythrough.scenario_snapshot || {};
    const worldData = (snapshot.world_data ?? {}) as NewbieWorldData;
    const setupSchema = (snapshot.setup_schema ?? []) as SetupSchemaField[];
    const customFields = buildCustomFields(setupMap, setupSchema);

    const turns: TurnLogItem[] = (turnsData?.items ?? []).map((turn) => ({
      id: turn.turn_id,
      turn_number: turn.turn_number,
      action_mode: "do",
      action_text: turn.action_text,
      narration_text: turn.narration_text ?? "",
      created_at: turn.created_at,
    }));

    const canAct = computeCanAct(
      serverPlaythrough.participants,
      serverPlaythrough.participant_id,
      serverPlaythrough.turn_count,
    );

    const playthroughData: PlaythroughData = {
      playthrough_id: serverPlaythrough.playthrough_id,
      scenario_id: serverPlaythrough.scenario_id,
      scenario_title: serverPlaythrough.scenario_title,
      creator_name: "Scenario Creator",
      opening_premise:
        worldData.openingPrompt ||
        worldData.singleLorePrompt ||
        "Your chronicle begins...",
      world_lore:
        worldData.worldLore ||
        worldData.singleLorePrompt ||
        "No world lore recorded.",
      key_facts: (worldData.facts ?? []).map((fact) => fact.text),
      story_cards: (worldData.storyCards ?? []).map(
        (card): StoryCard => ({
          id: card.id,
          title: card.name,
          category: card.type,
          content: card.content,
        }),
      ),
      character_name: (setupMap.character_name as string) || "Adventurer",
      custom_fields: customFields,
      turns,
      is_spectator: isSpectatorMode,
      participant_id: isSpectatorMode
        ? null
        : serverPlaythrough.participant_id,
      can_act: canAct,
    };

    setPlaythrough(playthroughData);
  }, [serverPlaythrough, turnsData, isSpectatorMode, setPlaythrough]);

  if (id && isLoading) {
    return (
      <div className="min-h-screen w-full bg-zinc-950 flex flex-col items-center justify-center space-y-4">
        <div className="w-10 h-10 border-2 border-amber-500/30 border-t-amber-500 rounded-full animate-spin" />
        <p className="font-mono text-xs text-amber-500/80 tracking-widest uppercase">
          LOADING PLAYTHROUGH SESSION...
        </p>
      </div>
    );
  }

  if (id && isError) {
    return (
      <div className="min-h-screen w-full bg-zinc-950 text-zinc-100 flex flex-col items-center justify-center p-6 text-center space-y-4">
        <h1 className="font-serif text-2xl text-red-400 font-bold">
          Failed to Load Playthrough
        </h1>
        <p className="font-mono text-xs text-zinc-400 max-w-sm">
          The requested playthrough session could not be retrieved from the
          server.
        </p>
      </div>
    );
  }

  return <PlayScreen />;
}

/** Solo playthroughs always allow acting. Multiplayer cycles by turn_order_position. */
function computeCanAct(
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

export default PlayPage;
