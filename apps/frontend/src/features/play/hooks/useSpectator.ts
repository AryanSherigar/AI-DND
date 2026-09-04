import { useCallback, useState } from "react";
import { useSSE } from "@/shared/hooks/useSSE";

import { ScenarioMood } from "../types/audio.types";
import { ambientSoundtrack } from "@/shared/lib/audio/ambient-soundtrack";

const TRS_BASE_URL = import.meta.env.VITE_TRS_URL || "http://localhost:8001";

export interface SpectatorEvent {
  eventName: "narration" | "done" | "degraded" | "mood";
  data: string;
}

/** Read-only live narration stream for spectators, gated on a share token. */
export function useSpectator(
  playthroughId: string | null,
  shareToken: string | null,
) {
  const [streamingText, setStreamingText] = useState("");
  const [isLive, setIsLive] = useState(false);

  const handleEvent = useCallback((eventName: string, data: string) => {
    if (eventName === "mood") {
      ambientSoundtrack.transitionTo(data as ScenarioMood);
    } else if (eventName === "narration") {
      setIsLive(true);
      setStreamingText((prev) => prev + data);
    } else if (eventName === "done") {
      setIsLive(false);
      setStreamingText("");
    }
  }, []);

  const url =
    playthroughId && shareToken
      ? `${TRS_BASE_URL}/v1/session/${playthroughId}/spectate?share_token=${encodeURIComponent(shareToken)}`
      : null;

  const status = useSSE(url, handleEvent, Boolean(url));

  return { streamingText, isLive, status };
}
