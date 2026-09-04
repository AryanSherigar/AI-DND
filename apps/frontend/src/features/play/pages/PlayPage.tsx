import { useEffect } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { MapViewer } from "../components/MapViewer/MapViewer";
import { PlayScreen } from "../components/PlayScreen/PlayScreen";
import { usePlayStore } from "../stores/play.store";
import { usePlaythrough } from "../hooks/usePlaythrough";
import { usePlaythroughTurns } from "../hooks/useTurns";
import { useNotifications } from "../hooks/useNotifications";
import { ambientSoundtrack } from "@/shared/lib/audio/ambient-soundtrack";
import {
  buildMasterPlaythroughData,
  buildNewbiePlaythroughData,
} from "./playthroughDataBuilders";

export function PlayPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const setPlaythrough = usePlayStore((s) => s.setPlaythrough);
  const queryClient = useQueryClient();

  const { data: serverPlaythrough, isLoading, isError } = usePlaythrough(id);
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
    return () => {
      ambientSoundtrack.stop();
    };
  }, []);

  useEffect(() => {
    if (!serverPlaythrough) return;

    const mode =
      (serverPlaythrough.scenario_snapshot?.mode as "newbie" | "master") ||
      "newbie";
    const playthroughData =
      mode === "master"
        ? buildMasterPlaythroughData(
            serverPlaythrough,
            turnsData,
            isSpectatorMode,
          )
        : buildNewbiePlaythroughData(
            serverPlaythrough,
            turnsData,
            isSpectatorMode,
          );

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

  return (
    <>
      <PlayScreen />
      <MapViewer
        scenarioSnapshot={serverPlaythrough?.scenario_snapshot}
        state={serverPlaythrough?.state}
      />
    </>
  );
}

export default PlayPage;
