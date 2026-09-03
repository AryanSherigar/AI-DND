import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ExpressionBuilder } from "./ExpressionBuilder";
import { AvailableField, FieldExpression } from "./ExpressionBuilder.types";

const AVAILABLE_FIELDS: AvailableField[] = [
  { path: "player.health", label: "Health", type: "number" },
  { path: "the_warden.awareness", label: "Awareness", type: "number" },
];

const Harness: React.FC<{
  onChange: (expr: FieldExpression | null) => void;
}> = ({ onChange }) => {
  const [value, setValue] = React.useState<FieldExpression | null>(null);

  const handleChange = (expr: FieldExpression | null): void => {
    setValue(expr);
    onChange(expr);
  };

  return (
    <ExpressionBuilder
      value={value}
      onChange={handleChange}
      availableFields={AVAILABLE_FIELDS}
    />
  );
};

describe("ExpressionBuilder", () => {
  it("builds { field: 'player.health', op: '<=', value: 0 } from the three pickers", async () => {
    const user = userEvent.setup();
    const handleChange = vi.fn();
    render(<Harness onChange={handleChange} />);

    const fieldInput = screen.getByPlaceholderText("player.health");
    await user.clear(fieldInput);
    await user.type(fieldInput, "player.health");

    const operatorSelect = screen.getAllByRole("combobox")[1];
    await user.selectOptions(operatorSelect, "<=");

    const valueInput = screen.getByRole("spinbutton");
    await user.type(valueInput, "0");

    const lastCall =
      handleChange.mock.calls[handleChange.mock.calls.length - 1];
    expect(lastCall[0]).toEqual({
      field: "player.health",
      op: "<=",
      value: 0,
    });
  });

  it("shows an inline error immediately for a field path that does not exist", async () => {
    const user = userEvent.setup();
    render(<Harness onChange={vi.fn()} />);

    const fieldInput = screen.getByPlaceholderText("player.health");
    await user.type(fieldInput, "player.nonexistent");

    expect(
      await screen.findByText("This field does not exist."),
    ).toBeInTheDocument();
  });
});
