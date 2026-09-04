import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DiceRollCard } from "../EBook/DiceRollCard";

describe("DiceRollCard", () => {
  it("renders the roll expression and total", () => {
    render(
      <DiceRollCard
        roll={{ expression: "d20+3", sides: 20, modifier: 3, roll: 10, total: 13 }}
      />,
    );

    expect(screen.getByText("d20+3")).toBeInTheDocument();
    expect(screen.getByText("13")).toBeInTheDocument();
  });
});
