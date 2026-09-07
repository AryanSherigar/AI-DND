import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useSSE } from "./useSSE";
import { SSEHandlers } from "../lib/sse-client";

let capturedHandlers: SSEHandlers | null = null;

vi.mock("../lib/sse-client", () => ({
  createGetSSEConnection: (
    _url: string,
    _token: string | null,
    handlers: SSEHandlers,
  ) => {
    capturedHandlers = handlers;
    return vi.fn();
  },
}));

describe("useSSE", () => {
  it("transitions status to closed when the connection ends without an error", async () => {
    const { result } = renderHook(() =>
      useSSE("https://example.test/stream", vi.fn()),
    );

    await waitFor(() => expect(capturedHandlers).not.toBeNull());
    capturedHandlers!.onOpen?.();
    await waitFor(() => expect(result.current).toBe("open"));

    capturedHandlers!.onClose?.();
    await waitFor(() => expect(result.current).toBe("closed"));
  });
});
