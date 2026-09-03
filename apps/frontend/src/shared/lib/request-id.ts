/**
 * Correlation ID generation for cross-service log tracing (see docs/logging.md).
 * The frontend generates the ID — not core-api — because turn submission
 * calls TRS directly, bypassing core-api entirely.
 */

export const REQUEST_ID_HEADER = "X-Request-Id";

export function generateRequestId(): string {
  return crypto.randomUUID();
}

let currentRequestId: string | null = null;

/** Set once per user action, so the frontend logger can tag buffered events with it. */
export function setCurrentRequestId(requestId: string): void {
  currentRequestId = requestId;
}

export function getCurrentRequestId(): string | null {
  return currentRequestId;
}
