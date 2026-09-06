import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { usePlayStore } from "../../../../stores/play.store";
import { TurnLogItem } from "../../../../types/play.types";
import { EBookTurnEntry } from "../EBookTurnEntry";

const mockTurn: TurnLogItem = {
  id: "turn-1",
  turn_number: 1,
  action_mode: "do",
  action_text: "I inspect the ancient altar.",
  narration_text:
    "Dust falls from the ceiling as shadows flicker across the stones.",
  created_at: new Date().toISOString(),
};

describe("EBookTurnEntry — narration font application", () => {
  beforeEach(() => {
    usePlayStore.setState({
      reader_font_override: null,
      playthrough: null,
    });
  });

  it("applies default narration font class to narration paragraphs", () => {
    render(
      <EBookTurnEntry
        turn={mockTurn}
        turnIndex={0}
        isLatest={true}
        knownEntities={[]}
        onSelectEntity={vi.fn()}
      />,
    );

    const paragraph = screen.getByText(/dust falls from the ceiling/i);
    expect(paragraph).toHaveClass("font-narration-im-fell-english");

    const actionQuote = screen.getByText(/"I inspect the ancient altar."/i);
    expect(actionQuote).not.toHaveClass("font-narration-im-fell-english");
    expect(actionQuote).toHaveClass("font-serif");
  });

  it("applies reader font override class to narration paragraphs when set", () => {
    usePlayStore.setState({
      reader_font_override: "special-elite",
    });

    render(
      <EBookTurnEntry
        turn={mockTurn}
        turnIndex={0}
        isLatest={true}
        knownEntities={[]}
        onSelectEntity={vi.fn()}
      />,
    );

    const paragraph = screen.getByText(/dust falls from the ceiling/i);
    expect(paragraph).toHaveClass("font-narration-special-elite");
  });
});
