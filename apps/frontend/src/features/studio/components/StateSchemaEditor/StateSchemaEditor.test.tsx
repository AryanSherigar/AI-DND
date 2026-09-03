import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
import { StateSchemaEditor } from "./StateSchemaEditor";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";

const renderStateSchemaEditor = (): void => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <StateSchemaEditor scenarioId={SCENARIO_ID} />
    </QueryClientProvider>,
  );
};

describe("StateSchemaEditor", () => {
  it("builds a nested object field with a primitive field inside it and saves the exact shape", async () => {
    let savedPayload: unknown = null;
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}`, () =>
        HttpResponse.json({ scenario_id: SCENARIO_ID, state_schema: {} }),
      ),
      http.patch(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}`,
        async ({ request }) => {
          savedPayload = await request.json();
          return HttpResponse.json({
            scenario_id: SCENARIO_ID,
            ...(savedPayload as Record<string, unknown>),
          });
        },
      ),
    );

    const user = userEvent.setup();
    renderStateSchemaEditor();

    await user.click(await screen.findByRole("button", { name: /add field/i }));

    await user.clear(screen.getByLabelText(/field key/i));
    await user.type(screen.getByLabelText(/field key/i), "player");
    await user.tab();

    await user.selectOptions(screen.getByLabelText(/field type/i), "object");

    const addFieldButtons = await screen.findAllByRole("button", {
      name: /add field/i,
    });
    await user.click(addFieldButtons[addFieldButtons.length - 1]);

    const keyInputs = screen.getAllByLabelText(/field key/i);
    const nestedKeyInput = keyInputs[keyInputs.length - 1];
    await user.clear(nestedKeyInput);
    await user.type(nestedKeyInput, "health");
    await user.tab();

    const typeSelects = screen.getAllByLabelText(/field type/i);
    await user.selectOptions(typeSelects[typeSelects.length - 1], "number");

    const labelInputs = screen.getAllByLabelText(/field label/i);
    await user.type(labelInputs[labelInputs.length - 1], "Health");

    const minInputs = screen.getAllByLabelText(/field min/i);
    await user.type(minInputs[minInputs.length - 1], "0");

    const maxInputs = screen.getAllByLabelText(/field max/i);
    await user.type(maxInputs[maxInputs.length - 1], "100");

    const initialInputs = screen.getAllByLabelText(/field initial value/i);
    await user.type(initialInputs[initialInputs.length - 1], "100");

    await user.click(screen.getByRole("button", { name: /^save$/i }));

    expect(savedPayload).toEqual({
      state_schema: {
        player: {
          type: "object",
          min: undefined,
          max: undefined,
          entity_type: undefined,
          item_type: undefined,
          fields: {
            health: {
              type: "number",
              initial: 100,
              label: "Health",
              min: 0,
              max: 100,
            },
          },
        },
      },
    });
  });
});
