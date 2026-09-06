import { useCallback, useEffect, useState } from "react";

export type ReplitHandshakeStatus = "waiting" | "ready" | "timed_out";

export interface ReplitHandshakeOutcome {
  outcome_tag: "win" | "lose";
  score?: number;
}

export interface UseReplitHandshakeResult {
  status: ReplitHandshakeStatus;
  outcome: ReplitHandshakeOutcome | null;
  /** Bump into the embedded iframe's `key` prop to force a reload on retry. */
  attempt: number;
  retry: () => void;
}

interface RawHandshakeMessage {
  type: "minigame:ready" | "minigame:result";
  outcome_tag?: unknown;
  score?: unknown;
}

function isRawHandshakeMessage(data: unknown): data is RawHandshakeMessage {
  if (typeof data !== "object" || data === null || !("type" in data)) {
    return false;
  }
  const type = (data as { type: unknown }).type;
  return type === "minigame:ready" || type === "minigame:result";
}

function parseOutcome(
  message: RawHandshakeMessage,
): ReplitHandshakeOutcome | null {
  const tag = message.outcome_tag;
  if (tag !== "win" && tag !== "lose") return null;
  const score = typeof message.score === "number" ? message.score : undefined;
  return { outcome_tag: tag, score };
}

/**
 * Validates and listens for the minigame-embed postMessage handshake from a
 * sandboxed Replit iframe: "minigame:ready" on load, "minigame:result" on
 * completion (see replit-template/minigame-sdk.js and
 * docs/specs/master-mode-minigames.spec.md §2/§3.4 for the full contract).
 * Shared between Studio's Test Connection button and Play's live embed —
 * genuinely feature-agnostic postMessage infrastructure, so it lives in
 * shared/ rather than under features/play/ or features/studio/, per
 * CLAUDE.md's feature-boundary rules.
 */
export function useReplitHandshake(
  iframeRef: React.RefObject<HTMLIFrameElement | null>,
  embedUrl: string | null,
  timeoutMs: number,
): UseReplitHandshakeResult {
  const [status, setStatus] = useState<ReplitHandshakeStatus>("waiting");
  const [outcome, setOutcome] = useState<ReplitHandshakeOutcome | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!embedUrl) return undefined;
    setStatus("waiting");
    setOutcome(null);

    let expectedOrigin: string;
    try {
      expectedOrigin = new URL(embedUrl).origin;
    } catch {
      setStatus("timed_out");
      return undefined;
    }

    const handleMessage = (event: MessageEvent): void => {
      // Both checks required: origin alone doesn't prove the message came
      // from *this* embedded iframe (another same-origin frame could send
      // one), and source alone doesn't validate the origin claim.
      if (event.source !== iframeRef.current?.contentWindow) return;
      if (event.origin !== expectedOrigin) return;
      if (!isRawHandshakeMessage(event.data)) return;

      if (event.data.type === "minigame:ready") {
        setStatus("ready");
      } else {
        const parsed = parseOutcome(event.data);
        if (parsed) setOutcome(parsed);
      }
    };

    window.addEventListener("message", handleMessage);
    const timeoutId = window.setTimeout(() => {
      setStatus((current) => (current === "ready" ? current : "timed_out"));
    }, timeoutMs);

    return () => {
      window.removeEventListener("message", handleMessage);
      window.clearTimeout(timeoutId);
    };
  }, [embedUrl, timeoutMs, attempt, iframeRef]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  return { status, outcome, attempt, retry };
}
