import { renderHook, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { useSpectator } from "./useSpectator";
import { queryClient } from "@/shared/lib/query-client";
import { SSEHandlers } from "@/shared/lib/sse-client";

let capturedHandlers: SSEHandlers | null = null;

vi.mock("@/shared/lib/sse-client", () => ({
  createGetSSEConnection: (
    _url: string,
    _token: string | null,
    handlers: SSEHandlers,
  ) => {
    capturedHandlers = handlers;
    return vi.fn();
  },
}));

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("useSpectator", () => {
  it("invalidates playthrough-turns when the stream reports done", async () => {
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    renderHook(() => useSpectator("pt-1", "share-token"), { wrapper });

    await waitFor(() => expect(capturedHandlers).not.toBeNull());
    capturedHandlers!.onEvent("narration", "The torches gutter.");
    capturedHandlers!.onEvent("done", "");

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["playthrough-turns", "pt-1"],
    });

    invalidateSpy.mockRestore();
  });
});
