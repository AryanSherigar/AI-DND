import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { SetupStageCard } from "../SetupStageCard";

describe("SetupStageCard", () => {
  const mockScenario = {
    id: "scen-1",
    scenario_id: "scen-1",
    title: "Echoes of the Void",
    setup_schema: [
      {
        id: "field-1",
        key: "character_name",
        label: "Hero Name",
        type: "text",
        is_character_name: true,
        required: true,
      },
      {
        id: "field-2",
        key: "class",
        label: "Character Class",
        type: "single_select",
        predicate: "is_class",
        options: [
          { id: "opt-1", label: "Mage", value: "mage" },
          { id: "opt-2", label: "Ranger", value: "ranger" },
        ],
        required: true,
      },
    ],
  };

  it("renders the protagonist badge and handles submission with formValues", async () => {
    const user = userEvent.setup();
    const handleSubmit = vi.fn();

    render(
      <MemoryRouter>
        <SetupStageCard scenario={mockScenario} onSubmit={handleSubmit} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Echoes of the Void")).toBeInTheDocument();
    expect(screen.getByText("PROTAGONIST")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/enter your character name/i),
    ).toBeInTheDocument();

    const nameInput = screen.getByPlaceholderText(/enter your character name/i);
    await user.type(nameInput, "Kaelen");

    const classSelect = screen.getByRole("combobox");
    await user.selectOptions(classSelect, "ranger");

    const submitButton = screen.getByRole("button", {
      name: /embark on journey/i,
    });
    await user.click(submitButton);

    expect(handleSubmit).toHaveBeenCalledTimes(1);
    const [, formValues] = handleSubmit.mock.calls[0];
    expect(formValues).toEqual({
      character_name: "Kaelen",
      class: "ranger",
    });
  });

  it("shows error when required field is missing", async () => {
    const user = userEvent.setup();
    const handleSubmit = vi.fn();

    render(
      <MemoryRouter>
        <SetupStageCard scenario={mockScenario} onSubmit={handleSubmit} />
      </MemoryRouter>,
    );

    const submitButton = screen.getByRole("button", {
      name: /embark on journey/i,
    });
    await user.click(submitButton);

    expect(handleSubmit).not.toHaveBeenCalled();
    expect(
      screen.getByText(/selection required for hero name/i),
    ).toBeInTheDocument();
  });
});
