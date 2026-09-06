import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { usePlayStore } from "../../../stores/play.store";
import { MinigameOverlay } from "../MinigameOverlay";

// DodgeMinigame is built by a concurrent workstream against
// docs/specs/dodge-minigame-design.spec.md and does not exist on disk yet —
// mocked here purely so this file's import graph resolves; MinigameOverlay's
// dodge branch itself is out of scope for this task.
vi.mock("../DodgeMinigame/DodgeMinigame", () => ({
  DodgeMinigame: () => <div data-testid="dodge-minigame-stub" />,
}));

vi.mock("../ReplitEmbed/ReplitEmbedMinigame", () => ({
  ReplitEmbedMinigame: () => <div data-testid="replit-embed-stub" />,
}));

function resetStore(): void {
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
});
