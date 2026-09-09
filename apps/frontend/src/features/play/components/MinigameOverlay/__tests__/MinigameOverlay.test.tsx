import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { usePlayStore } from "../../../stores/play.store";
import { MinigameOverlay } from "../MinigameOverlay";

// Mocked here purely so this file's import graph resolves; MinigameOverlay's
// dodge/replit_embed branches themselves are out of scope for this test file.
vi.mock("@/shared/components/minigames/DodgeMinigame/DodgeMinigame", () => ({
  DodgeMinigame: () => <div data-testid="dodge-minigame-stub" />,
}));

vi.mock(
  "@/shared/components/minigames/ReplitEmbed/ReplitEmbedMinigame",
  () => ({
    ReplitEmbedMinigame: () => <div data-testid="replit-embed-stub" />,
  }),
);

vi.mock("@/shared/hooks/useDefaultMoodTracks", () => ({
  useDefaultMoodTracks: () => ({ data: undefined }),
}));

const mockSubmit = vi.fn();
vi.mock("../../../hooks/useMinigameResult", () => ({
  useMinigameResult: () => ({
    submit: mockSubmit,
    retry: vi.fn(),
    submitTimeoutFallback: vi.fn(),
  }),
}));

function resetStore(): void {
  mockSubmit.mockClear();
  usePlayStore.setState({
    active_minigame: null,
  });
}

describe("MinigameOverlay", () => {
  beforeEach(() => {
    resetStore();
  });

  it("renders nothing when active_minigame is null", () => {
    const { container } = render(<MinigameOverlay />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the replit embed branch when active_minigame is a replit_embed minigame", () => {
    usePlayStore.setState({
      active_minigame: {
        minigame_id: "mg-1",
        minigame_type: "replit_embed",
        label: "Rune Puzzle",
        dodge_config: null,
        replit_embed_url: "https://example.replit.dev",
        timeout_seconds: 20,
      },
    });

    render(<MinigameOverlay />);
    expect(screen.getByTestId("replit-embed-stub")).toBeInTheDocument();
  });

  it("renders the dodge branch when active_minigame is a dodge minigame", () => {
    usePlayStore.setState({
      active_minigame: {
        minigame_id: "mg-2",
        minigame_type: "dodge",
        label: "Warden's Onslaught",
        dodge_config: { difficulty: 3 },
        replit_embed_url: null,
        timeout_seconds: 30,
      },
    });

    render(<MinigameOverlay />);
    expect(screen.getByTestId("dodge-minigame-stub")).toBeInTheDocument();
  });

  it("renders the top bar header with label and allows forfeiting as a timeout", () => {
    usePlayStore.setState({
      active_minigame: {
        minigame_id: "mg-1",
        minigame_type: "replit_embed",
        label: "Rune Strike Challenge",
        dodge_config: null,
        replit_embed_url: "https://example.replit.dev",
        timeout_seconds: 20,
        attempt_id: "attempt-123",
      },
    });

    render(<MinigameOverlay />);
    expect(screen.getByText("Rune Strike Challenge")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /forfeit/i })).toBeInTheDocument();

    // Click Forfeit to open confirmation modal
    fireEvent.click(screen.getByRole("button", { name: /forfeit/i }));
    expect(screen.getByText(/Forfeit Challenge\?/i)).toBeInTheDocument();

    // Click "Keep Playing" to dismiss
    fireEvent.click(screen.getByRole("button", { name: /keep playing/i }));
    expect(screen.queryByText(/Forfeit Challenge\?/i)).not.toBeInTheDocument();
    expect(mockSubmit).not.toHaveBeenCalled();

    // Open again and confirm forfeit
    fireEvent.click(screen.getByRole("button", { name: /forfeit/i }));
    fireEvent.click(screen.getByRole("button", { name: /yes, forfeit/i }));

    expect(mockSubmit).toHaveBeenCalledWith({
      minigame_id: "mg-1",
      attempt_id: "attempt-123",
      outcome_tag: "timeout",
    });
  });
});
