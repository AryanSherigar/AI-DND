import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { IframeLoadingState } from "../IframeLoadingState";

describe("IframeLoadingState", () => {
  it("shows a spinner and no retry button while waiting", () => {
    render(
      <IframeLoadingState
        isTimedOut={false}
        canRetry={false}
        onRetry={vi.fn()}
      />,
    );

    expect(
      screen.getByText(/Connecting to the challenge/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("shows the retry button once timed out and retry is allowed", () => {
    const onRetry = vi.fn();
    render(
      <IframeLoadingState
        isTimedOut={true}
        canRetry={true}
        onRetry={onRetry}
      />,
    );

    const button = screen.getByRole("button", { name: /retry/i });
    fireEvent.click(button);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("hides the retry button once timed out but retry has been exhausted", () => {
    render(
      <IframeLoadingState
        isTimedOut={true}
        canRetry={false}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
