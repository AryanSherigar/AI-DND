import { useEffect, useRef, useState } from "react";
import { createGetSSEConnection, SSEHandlers } from "../lib/sse-client";
import { useAuthStore } from "@/features/auth/stores/auth.store";

export type SSEStatus = "idle" | "connecting" | "open" | "closed";

/**
 * React lifecycle wrapper around a persistent GET-based SSE connection.
 * Connects on mount (or when `enabled` becomes true / `url` changes) and
 * always disconnects on unmount — the only place besides sse-client.ts that
 * knows a streamed SSE connection exists.
 */
export function useSSE(
  url: string | null,
  onEvent: (eventName: string, data: string) => void,
  enabled: boolean = true,
): SSEStatus {
  const [status, setStatus] = useState<SSEStatus>("idle");
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;
  const accessToken = useAuthStore((s) => s.accessToken);

  useEffect(() => {
    if (!enabled || !url) {
      setStatus("idle");
      return;
    }

    setStatus("connecting");
    const handlers: SSEHandlers = {
      onEvent: (name, data) => onEventRef.current(name, data),
      onOpen: () => setStatus("open"),
      onError: () => setStatus("closed"),
    };
    const disconnect = createGetSSEConnection(url, accessToken, handlers);

    return () => {
      disconnect();
      setStatus("closed");
    };
  }, [url, enabled, accessToken]);

  return status;
}
