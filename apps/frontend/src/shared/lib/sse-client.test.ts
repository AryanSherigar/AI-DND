import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  createGetSSEConnection,
  createPostSSEConnection,
  SSEHandlers,
} from "./sse-client";

function createMockStream(chunks: string[]) {
  const encoder = new TextEncoder();
  let index = 0;
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(encoder.encode(chunks[index]));
        index++;
      } else {
        controller.close();
      }
    },
  });
}

describe("sse-client", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("parses events and ignores keepalive ping comments", async () => {
    const stream = createMockStream([
      ": ping - 2026-09-07T14:15:38Z\r\n\r\n",
      "event: narration\r\ndata: The cave is dark.\r\n\r\n",
      ": ping - 2026-09-07T14:15:53Z\r\n\r\n",
      "event: done\r\ndata: \r\n\r\n",
    ]);

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: stream,
      }),
    );

    const receivedEvents: Array<{ event: string; data: string }> = [];
    const handlers: SSEHandlers = {
      onEvent: (event, data) => receivedEvents.push({ event, data }),
    };

    const cleanup = createGetSSEConnection(
      "http://localhost:8001/v1/session/1/spectate",
      null,
      handlers,
    );

    await vi.advanceTimersByTimeAsync(0);
    expect(receivedEvents).toEqual([
      { event: "narration", data: "The cave is dark." },
      { event: "done", data: "" },
    ]);

    cleanup();
  });

  it("reconnects with backoff when a GET stream terminates unexpectedly", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        body: createMockStream(["event: msg\ndata: first\n\n"]),
      })
      .mockResolvedValueOnce({
        ok: true,
        body: createMockStream(["event: msg\ndata: second\n\n"]),
      });

    vi.stubGlobal("fetch", fetchMock);

    const receivedEvents: Array<{ event: string; data: string }> = [];
    const handlers: SSEHandlers = {
      onEvent: (event, data) => receivedEvents.push({ event, data }),
    };

    const cleanup = createGetSSEConnection(
      "http://localhost:8001/v1/session/1/spectate",
      null,
      handlers,
      undefined,
      { initialDelayMs: 500, maxDelayMs: 2000, backoffMultiplier: 2 },
    );

    await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(receivedEvents).toHaveLength(1);

    // Advance timer past initial retry delay
    await vi.advanceTimersByTimeAsync(500);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(receivedEvents).toHaveLength(2);
    expect(receivedEvents[1].data).toBe("second");

    cleanup();
  });

  it("stops reconnecting when cleanup is called", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: createMockStream(["event: msg\ndata: one\n\n"]),
    });
    vi.stubGlobal("fetch", fetchMock);

    const cleanup = createGetSSEConnection(
      "http://localhost:8001/v1/session/1/spectate",
      null,
      { onEvent: vi.fn() },
      undefined,
      { initialDelayMs: 500 },
    );

    await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Abort before retry timer fires
    cleanup();
    await vi.advanceTimersByTimeAsync(1000);

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not auto-reconnect for POST connections", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: createMockStream(["event: done\ndata: \n\n"]),
    });
    vi.stubGlobal("fetch", fetchMock);

    const cleanup = createPostSSEConnection(
      "http://localhost:8001/v1/turn",
      { action: "look" },
      null,
      { onEvent: vi.fn() },
    );

    await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(5000);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    cleanup();
  });
});
