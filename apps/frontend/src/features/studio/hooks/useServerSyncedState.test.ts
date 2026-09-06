import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useServerSyncedState } from "./useServerSyncedState";

describe("useServerSyncedState", () => {
  it("seeds local state from the server value once it arrives", () => {
    const { result, rerender } = renderHook(
      ({ serverValue }: { serverValue: string | undefined }) =>
        useServerSyncedState(serverValue),
      { initialProps: { serverValue: undefined as string | undefined } },
    );

    expect(result.current[0]).toBeUndefined();

    rerender({ serverValue: "Sunken Kingdom" });
    expect(result.current[0]).toBe("Sunken Kingdom");
  });

  it("picks up an external server change when the user hasn't edited locally", () => {
    const { result, rerender } = renderHook(
      ({ serverValue }: { serverValue: string | undefined }) =>
        useServerSyncedState(serverValue),
      {
        initialProps: { serverValue: "Original logline" as string | undefined },
      },
    );

    expect(result.current[0]).toBe("Original logline");

    rerender({ serverValue: "AI-applied logline" });
    expect(result.current[0]).toBe("AI-applied logline");
  });

  it("does not clobber an unsaved local edit when the server changes externally", () => {
    const { result, rerender } = renderHook(
      ({ serverValue }: { serverValue: string | undefined }) =>
        useServerSyncedState(serverValue),
      {
        initialProps: { serverValue: "Original logline" as string | undefined },
      },
    );

    act(() => {
      result.current[1]("User is mid-edit");
    });
    expect(result.current[0]).toBe("User is mid-edit");

    rerender({ serverValue: "AI-applied logline" });

    expect(result.current[0]).toBe("User is mid-edit");
  });

  it("reconciles cleanly once the user's own save lands in the server value", () => {
    const { result, rerender } = renderHook(
      ({ serverValue }: { serverValue: string | undefined }) =>
        useServerSyncedState(serverValue),
      {
        initialProps: { serverValue: "Original logline" as string | undefined },
      },
    );

    act(() => {
      result.current[1]("User's saved edit");
    });
    rerender({ serverValue: "User's saved edit" });
    expect(result.current[0]).toBe("User's saved edit");

    rerender({ serverValue: "Later AI update" });
    expect(result.current[0]).toBe("Later AI update");
  });
});
