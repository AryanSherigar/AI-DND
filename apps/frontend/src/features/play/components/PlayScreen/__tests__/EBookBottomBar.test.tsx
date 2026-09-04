import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EBookBottomBar } from "../EBook/EBookBottomBar";

describe("EBookBottomBar", () => {
  it("renders reader controls and handles action clicks", () => {
    const handleTakeAction = vi.fn();
    const handleContinue = vi.fn();
    const handleRetry = vi.fn();
    const handleEdit = vi.fn();
    const handleOpenCodex = vi.fn();

    render(
      <EBookBottomBar
        isNarrating={false}
        isSpectator={false}
        hasTurns={true}
        onTakeAction={handleTakeAction}
        onContinue={handleContinue}
        onRetry={handleRetry}
        onEditAction={handleEdit}
        onOpenCodex={handleOpenCodex}
      />,
    );

    const takeActionButton = screen.getByRole("button", {
      name: /Take Action/i,
    });
    fireEvent.click(takeActionButton);
    expect(handleTakeAction).toHaveBeenCalledTimes(1);

    const continueButton = screen.getByRole("button", { name: /Continue/i });
    fireEvent.click(continueButton);
    expect(handleContinue).toHaveBeenCalledTimes(1);

    const retryButton = screen.getByRole("button", { name: /Retry/i });
    fireEvent.click(retryButton);
    expect(handleRetry).toHaveBeenCalledTimes(1);

    const editButton = screen.getByRole("button", { name: /Edit/i });
    fireEvent.click(editButton);
    expect(handleEdit).toHaveBeenCalledTimes(1);
  });

  it("renders spectator message when isSpectator is true", () => {
    render(
      <EBookBottomBar
        isNarrating={false}
        isSpectator={true}
        hasTurns={false}
        onTakeAction={vi.fn()}
        onContinue={vi.fn()}
        onRetry={vi.fn()}
        onEditAction={vi.fn()}
        onOpenCodex={vi.fn()}
      />,
    );

    expect(
      screen.getByText(/You are currently spectating this chronicle/i),
    ).toBeInTheDocument();
  });

  it("renders a waiting message and no action trigger when canAct is false", () => {
    render(
      <EBookBottomBar
        isNarrating={false}
        isSpectator={false}
        hasTurns={false}
        canAct={false}
        waitingOnLabel="Player 2"
        onTakeAction={vi.fn()}
        onContinue={vi.fn()}
        onRetry={vi.fn()}
        onEditAction={vi.fn()}
        onOpenCodex={vi.fn()}
      />,
    );

    expect(screen.getByText(/Waiting for Player 2/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Take Action/i }),
    ).not.toBeInTheDocument();
  });

  it("renders an Open Character Sheet trigger only when onOpenCharacterSheet is passed", () => {
    const handleOpenCharacterSheet = vi.fn();
    render(
      <EBookBottomBar
        isNarrating={false}
        isSpectator={false}
        hasTurns={false}
        onTakeAction={vi.fn()}
        onContinue={vi.fn()}
        onRetry={vi.fn()}
        onEditAction={vi.fn()}
        onOpenCodex={vi.fn()}
        onOpenCharacterSheet={handleOpenCharacterSheet}
      />,
    );

    const characterButton = screen.getByTitle("Open Character Sheet");
    fireEvent.click(characterButton);
    expect(handleOpenCharacterSheet).toHaveBeenCalledTimes(1);
  });
});
