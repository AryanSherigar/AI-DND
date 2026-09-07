/**
 * The only file that reads a streamed fetch response body for SSE — every
 * SSE consumer in the app routes through here.
 *
 * Both GET and POST connections use fetch()'s streaming body rather than the
 * browser's native EventSource: EventSource cannot send a custom
 * Authorization header, and this app's auth (both Core API and TRS) is
 * Bearer-JWT-based, not cookie-based, so EventSource can't authenticate to
 * the notifications endpoint. Using one mechanism for both GET and POST also
 * keeps this file's parsing logic single-sourced.
 */
import { REQUEST_ID_HEADER } from "./request-id";

export interface SSEHandlers {
  onEvent: (eventName: string, data: string) => void;
  onError?: (error: unknown) => void;
  onOpen?: () => void;
  // Fires when the underlying connection ends without a fetch/network
  // error — including a server-side stream that closes mid-generation
  // (e.g. an unhandled exception after headers were already sent, so it
  // never reaches onError). Callers that expect an explicit terminal event
  // of their own (like TRS's "done"/"degraded") should treat a close
  // without having seen one as a failure, not a silent success.
  onClose?: () => void;
}

export interface SSERetryConfig {
  initialDelayMs: number;
  maxDelayMs: number;
  backoffMultiplier: number;
}

export const DEFAULT_RETRY_CONFIG: SSERetryConfig = {
  initialDelayMs: 1000,
  maxDelayMs: 15000,
  backoffMultiplier: 1.5,
};

function computeNextBackoff(
  currentDelay: number,
  config: SSERetryConfig,
): number {
  return Math.min(currentDelay * config.backoffMultiplier, config.maxDelayMs);
}

function createReconnectingHandlers(
  handlers: SSEHandlers,
  onResetDelay: () => void,
  onReconnect: () => void,
): SSEHandlers {
  return {
    ...handlers,
    onOpen: () => {
      onResetDelay();
      handlers.onOpen?.();
    },
    onClose: () => {
      handlers.onClose?.();
      onReconnect();
    },
    onError: (error: unknown) => {
      handlers.onError?.(error);
      onReconnect();
    },
  };
}

/** Persistent GET-based SSE connection (notifications, spectate streams). */
export function createGetSSEConnection(
  url: string,
  authToken: string | null,
  handlers: SSEHandlers,
  requestId?: string,
  retryConfig?: Partial<SSERetryConfig>,
): () => void {
  const config = { ...DEFAULT_RETRY_CONFIG, ...retryConfig };
  const controller = new AbortController();
  let retryTimer: ReturnType<typeof setTimeout> | null = null;
  let retryDelayMs = config.initialDelayMs;

  const reconnect = () => {
    if (controller.signal.aborted || retryTimer !== null) return;
    const currentDelay = retryDelayMs;
    retryDelayMs = computeNextBackoff(retryDelayMs, config);
    retryTimer = setTimeout(() => {
      retryTimer = null;
      connect();
    }, currentDelay);
  };

  const wrappedHandlers = createReconnectingHandlers(
    handlers,
    () => {
      retryDelayMs = config.initialDelayMs;
    },
    reconnect,
  );

  const connect = () => {
    if (controller.signal.aborted) return;
    void streamRequest(
      url,
      "GET",
      undefined,
      authToken,
      wrappedHandlers,
      controller.signal,
      requestId,
    );
  };

  connect();
  return () => {
    if (retryTimer !== null) clearTimeout(retryTimer);
    controller.abort();
  };
}

/** One-shot POST-then-stream SSE connection (TRS's POST /v1/turn). */
export function createPostSSEConnection(
  url: string,
  body: unknown,
  authToken: string | null,
  handlers: SSEHandlers,
  requestId?: string,
): () => void {
  return createFetchSSEConnection(
    url,
    "POST",
    body,
    authToken,
    handlers,
    requestId,
  );
}

function createFetchSSEConnection(
  url: string,
  method: "GET" | "POST",
  body: unknown,
  authToken: string | null,
  handlers: SSEHandlers,
  requestId?: string,
): () => void {
  const controller = new AbortController();
  void streamRequest(
    url,
    method,
    body,
    authToken,
    handlers,
    controller.signal,
    requestId,
  );
  return () => controller.abort();
}

// Mirrors shared/lib/api-client.ts's request interceptor: when there's no
// logged-in session, dev builds fall back to a fixed dev user id rather than
// going unauthenticated. Kept in sync with that file intentionally — SSE
// requests need the same fallback REST requests already get.
const DEV_USER_ID =
  import.meta.env.VITE_DEV_USER_ID || "464f4a91-86b5-47ce-b19a-19f37615230f";

function buildAuthHeaders(authToken: string | null): Record<string, string> {
  if (authToken) return { Authorization: `Bearer ${authToken}` };
  if (import.meta.env.DEV) return { "X-Dev-User-Id": DEV_USER_ID };
  return {};
}

function buildRequestIdHeader(requestId?: string): Record<string, string> {
  return requestId ? { [REQUEST_ID_HEADER]: requestId } : {};
}

async function streamRequest(
  url: string,
  method: "GET" | "POST",
  body: unknown,
  authToken: string | null,
  handlers: SSEHandlers,
  signal: AbortSignal,
  requestId?: string,
): Promise<void> {
  try {
    const response = await fetch(url, {
      method,
      headers: {
        ...(method === "POST" ? { "Content-Type": "application/json" } : {}),
        ...buildAuthHeaders(authToken),
        ...buildRequestIdHeader(requestId),
      },
      body: method === "POST" ? JSON.stringify(body) : undefined,
      signal,
    });
    if (!response.ok || !response.body) {
      handlers.onError?.(new Error(`SSE request failed: ${response.status}`));
      return;
    }
    handlers.onOpen?.();
    await readEventStream(response.body, handlers);
    handlers.onClose?.();
  } catch (error) {
    if (signal.aborted) return;
    handlers.onError?.(error);
  }
}

async function readEventStream(
  body: ReadableStream<Uint8Array>,
  handlers: SSEHandlers,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let isStreaming = true;
  while (isStreaming) {
    const { done, value } = await reader.read();
    if (done) {
      isStreaming = false;
      break;
    }
    // sse_starlette (the server) writes CRLF line endings, so frames are
    // separated by "\r\n\r\n", not "\n\n" — normalize before splitting.
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    buffer = consumeSSEFrames(buffer, handlers);
  }
}

/** Parses complete "event: x\ndata: y\n\n" blocks out of buffer, returning the remainder. */
function consumeSSEFrames(buffer: string, handlers: SSEHandlers): string {
  const frames = buffer.split("\n\n");
  const remainder = frames.pop() ?? "";
  for (const frame of frames) {
    const { event, data } = parseSSEFrame(frame);
    if (event) handlers.onEvent(event, data);
  }
  return remainder;
}

function parseSSEFrame(frame: string): { event: string | null; data: string } {
  let event: string | null = null;
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  return { event, data: dataLines.join("\n") };
}
