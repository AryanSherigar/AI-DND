import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { JudgeSignInButton } from "../JudgeSignInButton";

describe("JudgeSignInButton", () => {
  it("renders the button and demo credentials", () => {
    render(<JudgeSignInButton onClick={vi.fn()} />);

    expect(
      screen.getByRole("button", { name: /quick login as judge/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("judge@demo.com")).toBeInTheDocument();
  });

  it("calls onClick when clicked", () => {
    const handleClick = vi.fn();
    render(<JudgeSignInButton onClick={handleClick} />);

    fireEvent.click(
      screen.getByRole("button", { name: /quick login as judge/i }),
    );
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("disables the button and shows loader when isPending is true", () => {
    const handleClick = vi.fn();
    render(<JudgeSignInButton onClick={handleClick} isPending={true} />);

    const button = screen.getByRole("button", {
      name: /entering as judge/i,
    });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(handleClick).not.toHaveBeenCalled();
  });

  it("does not trigger onClick when disabled is true", () => {
    const handleClick = vi.fn();
    render(<JudgeSignInButton onClick={handleClick} disabled={true} />);

    const button = screen.getByRole("button", {
      name: /quick login as judge/i,
    });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(handleClick).not.toHaveBeenCalled();
  });
});
