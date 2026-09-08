import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useSSE } from "@/shared/hooks/useSSE";

import { ScenarioMood } from "@/shared/types/audio.types";
import { ambientSoundtrack } from "@/shared/lib/audio/ambient-soundtrack";
import { resolveMoodTrackUrl } from "@/shared/constants/audio";

const TRS_BASE_URL = import.meta.env.VITE_TRS_URL || "http://localhost:8001";

export interface SpectatorEvent {
  eventName: "narration" | "done" | "degraded" | "mood";
  data: string;
}

/** Read-only live narration stream for spectators, gated on a share token. */
export function useSpectator(
  playthroughId: string | null,
  shareToken: string | null,
  musicTracks?: Partial<Record<ScenarioMood, string | null>>,
) {
  const [streamingText, setStreamingText] = useState("");
  const [isLive, setIsLive] = useState(false);
  const queryClient = useQueryClient();

  const handleEvent = useCallback(
    (eventName: string, data: string) => {
      if (eventName === "mood") {
        const mood = data as ScenarioMood;
        ambientSoundtrack.transitionTo(
          mood,
          resolveMoodTrackUrl(mood, musicTracks),
        );
      } else if (eventName === "narration") {
        setIsLive(true);
        setStreamingText((prev) => prev + data);
      } else if (eventName === "done") {
        setIsLive(false);
        if (playthroughId) {
          void queryClient.invalidateQueries({
            queryKey: ["playthrough-turns", playthroughId],
          });
        }
        setStreamingText("");
      }
    },
    [playthroughId, queryClient, musicTracks],
  );

  const url =
    playthroughId && shareToken
      ? `${TRS_BASE_URL}/v1/session/${playthroughId}/spectate?share_token=${encodeURIComponent(shareToken)}`
      : null;

  const status = useSSE(url, handleEvent, Boolean(url));

  return { streamingText, isLive, status };
}
