import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChapterSummaryStrip } from "../EBook/ChapterSummaryStrip";
import { ChapterDelta } from "../../../types/play.types";

describe("ChapterSummaryStrip", () => {
  it("renders stat changes and inventory changes", () => {
    const delta: ChapterDelta = {
      stat_changes: [
        { path: "player.health", label: "Health", before: 100, after: 85, delta: -15 },
      ],
      inventory_changes: [
        { path: "player.inventory", entity_id: "sword-1", entity_display_name: "Rusty Sword" },
      ],
      dice_rolls: [],
    };

    render(<ChapterSummaryStrip delta={delta} />);

    expect(screen.getByText(/Health/i)).toBeInTheDocument();
    expect(screen.getByText("-15")).toBeInTheDocument();
    expect(screen.getByText(/\+Rusty Sword/i)).toBeInTheDocument();
  });

  it("renders nothing when the delta has no content", () => {
    const delta: ChapterDelta = {
      stat_changes: [],
      inventory_changes: [],
      dice_rolls: [],
    };

    const { container } = render(<ChapterSummaryStrip delta={delta} />);
    expect(container).toBeEmptyDOMElement();
  });
});
