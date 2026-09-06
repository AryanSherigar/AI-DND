import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SpectatorView } from "../SpectatorView";
import { TurnLogResponse } from "../../../api/turns.api";

const mockTurn: TurnLogResponse = {
  turn_id: "turn-1",
  playthrough_id: "pt-1",
  turn_number: 1,
  action_text: "I open the chest.",
  narration_text: "Gold coins spill across the mossy stone floor.",
  participant_id: null,
  tool_calls: [],
  created_at: new Date().toISOString(),
};

describe("SpectatorView", () => {
  it("renders scenario title and turns with scenario narration font", () => {
    render(
      <SpectatorView
        scenarioTitle="The Sunken Crypt"
        turns={[mockTurn]}
        streamingText=""
        isLive={true}
        narrationFont="cinzel"
      />,
    );

    expect(screen.getByText("The Sunken Crypt")).toBeInTheDocument();
    const narrationParagraph = screen.getByText(
      /gold coins spill across the mossy stone floor/i,
    );
    expect(narrationParagraph).toHaveClass("font-narration-cinzel");
  });

  it("applies scenario narration font to live streaming text", () => {
    render(
      <SpectatorView
        scenarioTitle="The Sunken Crypt"
        turns={[]}
        streamingText="A dark presence looms..."
        isLive={true}
        narrationFont="special-elite"
      />,
    );

    const streamingParagraph = screen.getByText(/a dark presence looms/i);
    expect(streamingParagraph).toHaveClass("font-narration-special-elite");
  });
});
