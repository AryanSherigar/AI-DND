import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { EnterNowButton } from "../EnterNowButton";

describe("EnterNowButton", () => {
  it("renders the button with ENTER NOW text", () => {
    render(<EnterNowButton />);
    expect(
      screen.getByRole("button", { name: /enter now/i }),
    ).toBeInTheDocument();
  });

  it("calls onClick when clicked", async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();

    render(<EnterNowButton onClick={handleClick} />);

    await user.click(screen.getByRole("button", { name: /enter now/i }));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
