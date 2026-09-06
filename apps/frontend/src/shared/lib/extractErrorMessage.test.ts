import { describe, expect, it } from "vitest";
import { extractErrorMessage } from "./extractErrorMessage";

const buildAxiosError = (data?: unknown, message = "Request failed"): Error => {
  const error = new Error(message) as Error & {
    response?: { data?: unknown };
  };
  if (data !== undefined) error.response = { data };
  return error;
};

describe("extractErrorMessage", () => {
  it("returns the fallback for a non-error value", () => {
    expect(extractErrorMessage("not an error", "fallback")).toBe("fallback");
  });

  it("returns a plain string detail as-is", () => {
    const err = buildAxiosError({ detail: "Duplicate entity name." });
    expect(extractErrorMessage(err, "fallback")).toBe("Duplicate entity name.");
  });

  it("formats a FastAPI 422 validation error list into a readable message", () => {
    const err = buildAxiosError({
      detail: [
        {
          loc: ["body", "logline"],
          msg: "String should have at most 150 characters",
          type: "string_too_long",
        },
      ],
    });
    expect(extractErrorMessage(err, "fallback")).toBe(
      "logline: String should have at most 150 characters",
    );
  });

  it("joins multiple validation errors", () => {
    const err = buildAxiosError({
      detail: [
        { loc: ["body", "logline"], msg: "Too long" },
        { loc: ["body", "title"], msg: "Required" },
      ],
    });
    expect(extractErrorMessage(err, "fallback")).toBe(
      "logline: Too long; title: Required",
    );
  });

  it("falls back to the error message when detail is missing", () => {
    const err = buildAxiosError(undefined, "Network error");
    expect(extractErrorMessage(err, "fallback")).toBe("Network error");
  });

  it("falls back to the provided fallback when nothing else is usable", () => {
    const err = new Error("");
    expect(extractErrorMessage(err, "fallback")).toBe("fallback");
  });
});
