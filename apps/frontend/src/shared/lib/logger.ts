/**
 * Client-side structured logger. Buffers events and batches them to
 * POST /v1/logs on core-api, which re-emits them through the same
 * structlog pipeline (and redaction) backend logs already flow through.
 * See docs/logging.md for retention/sampling policy.
 */
import { apiClient } from "./api-client";
import { getCurrentRequestId } from "./request-id";
import type { LogEvent, LogLevel } from "@/shared/types/logging.types";

const LOGS_ENDPOINT = "/v1/logs";
const MAX_BATCH_SIZE = 20;
const FLUSH_INTERVAL_MS = 5000;

const sessionId = crypto.randomUUID();
let buffer: LogEvent[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;

export function logEvent(
  level: LogLevel,
  event: string,
  fields: Record<string, unknown> = {},
): void {
  buffer.push({
    level,
    event,
    request_id: getCurrentRequestId(),
    session_id: sessionId,
    client_timestamp: new Date().toISOString(),
    fields,
  });

  if (buffer.length >= MAX_BATCH_SIZE) {
    flush();
    return;
  }
  scheduleFlush();
}

function scheduleFlush(): void {
  if (flushTimer) return;
  flushTimer = setTimeout(flush, FLUSH_INTERVAL_MS);
}

function flush(): void {
  if (flushTimer) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }
  if (buffer.length === 0) return;

  const entries = buffer;
  buffer = [];
  // Best-effort: this is a debug aid, not a durable record, so failures are
  // dropped rather than retried (avoids unbounded growth if the endpoint is down).
  void apiClient.post(LOGS_ENDPOINT, { entries }).catch(() => undefined);
}

function flushOnUnload(): void {
  if (buffer.length === 0) return;
  const entries = buffer;
  buffer = [];
  const baseURL = apiClient.defaults.baseURL ?? "";
  navigator.sendBeacon(
    `${baseURL}${LOGS_ENDPOINT}`,
    new Blob([JSON.stringify({ entries })], { type: "application/json" }),
  );
}

window.addEventListener("beforeunload", flushOnUnload);
