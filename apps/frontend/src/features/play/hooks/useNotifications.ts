import { useCallback, useState } from "react";
import { useSSE } from "@/shared/hooks/useSSE";

const TRS_BASE_URL = import.meta.env.VITE_TRS_URL || "http://localhost:8001";

/**
 * Multiplayer turn-order notifications (persistent GET SSE channel).
 * Solo playthroughs should pass enabled=false — this channel is unused there.
 */
export function useNotifications(
  playthroughId: string | null,
  participantId: string | null,
  enabled: boolean,
) {
  const [isMyTurnSignal, setIsMyTurnSignal] = useState(false);

  const handleEvent = useCallback((eventName: string) => {
    if (eventName === "your_turn") setIsMyTurnSignal(true);
  }, []);

  const url =
    playthroughId && participantId
      ? `${TRS_BASE_URL}/v1/session/${playthroughId}/notifications?participant_id=${participantId}`
      : null;

  const status = useSSE(url, handleEvent, enabled && Boolean(url));

  const acknowledgeMyTurn = useCallback(() => setIsMyTurnSignal(false), []);

  return { isMyTurnSignal, acknowledgeMyTurn, status };
}
