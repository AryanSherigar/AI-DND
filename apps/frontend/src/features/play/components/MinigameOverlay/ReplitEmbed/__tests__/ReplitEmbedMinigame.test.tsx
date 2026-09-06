import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { ReplitEmbedMinigame } from "../ReplitEmbedMinigame";

const EMBED_URL = "https://demo-repl.example.dev/game";
const TIMEOUT_SECONDS = 5;

function getIframe(): HTMLIFrameElement {
  const iframe = document.querySelector("iframe");
  if (!iframe) throw new Error("iframe not found");
  return iframe;
}

function postHandshakeMessage(
  data: Record<string, unknown>,
  origin: string = new URL(EMBED_URL).origin,
): void {
  const iframe = getIframe();
  act(() => {
    window.dispatchEvent(
      new MessageEvent("message", {
        data,
        origin,
        source: iframe.contentWindow,
      }),
    );
  });
}

describe("ReplitEmbedMinigame", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows the loading state while waiting for the handshake", () => {
    render(
      <ReplitEmbedMinigame
        replitEmbedUrl={EMBED_URL}
        timeoutSeconds={TIMEOUT_SECONDS}
        onComplete={vi.fn()}
      />,
    );

    expect(
      screen.getByText(/Connecting to the challenge/i),
    ).toBeInTheDocument();
  });

  it("transitions to the timed-out state once the configured timeout elapses", () => {
    render(
      <ReplitEmbedMinigame
        replitEmbedUrl={EMBED_URL}
        timeoutSeconds={TIMEOUT_SECONDS}
        onComplete={vi.fn()}
      />,
    );

    act(() => {
      vi.advanceTimersByTime(TIMEOUT_SECONDS * 1000 + 1);
    });

    expect(screen.getByText(/did not respond in time/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("retries once, then auto-resolves to a timeout outcome on a second failure", () => {
    const onComplete = vi.fn();
    render(
      <ReplitEmbedMinigame
        replitEmbedUrl={EMBED_URL}
        timeoutSeconds={TIMEOUT_SECONDS}
        onComplete={onComplete}
      />,
    );

    act(() => {
      vi.advanceTimersByTime(TIMEOUT_SECONDS * 1000 + 1);
    });
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    // Back to waiting after the retry remounts the iframe.
    expect(
      screen.getByText(/Connecting to the challenge/i),
    ).toBeInTheDocument();
    expect(onComplete).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(TIMEOUT_SECONDS * 1000 + 1);
    });

    expect(onComplete).toHaveBeenCalledWith({ outcome_tag: "timeout" });
    // No further retry offered after auto-resolving.
    expect(
      screen.queryByRole("button", { name: /retry/i }),
    ).not.toBeInTheDocument();
  });

  it("calls onComplete with the result from a valid postMessage from the expected origin", () => {
    const onComplete = vi.fn();
    render(
      <ReplitEmbedMinigame
        replitEmbedUrl={EMBED_URL}
        timeoutSeconds={TIMEOUT_SECONDS}
        onComplete={onComplete}
      />,
    );

    postHandshakeMessage({
      type: "minigame:result",
      outcome_tag: "win",
      score: 42,
    });

    expect(onComplete).toHaveBeenCalledWith({
      outcome_tag: "win",
      score: 42,
    });
  });

  it("ignores a message from a mismatched origin", () => {
    const onComplete = vi.fn();
    render(
      <ReplitEmbedMinigame
        replitEmbedUrl={EMBED_URL}
        timeoutSeconds={TIMEOUT_SECONDS}
        onComplete={onComplete}
      />,
    );

    postHandshakeMessage(
      { type: "minigame:result", outcome_tag: "win", score: 99 },
      "https://attacker.example.com",
    );

    expect(onComplete).not.toHaveBeenCalled();
  });
});
