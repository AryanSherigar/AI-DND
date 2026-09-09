import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
import { ActionChipsEditor } from "./ActionChipsEditor";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";

const renderEditor = (): void => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ActionChipsEditor scenarioId={SCENARIO_ID} />
    </QueryClientProvider>,
  );
};

describe("ActionChipsEditor", () => {
  it("adds a chip and saves the action_chips array", async () => {
    let savedPayload: unknown = null;
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}`, () =>
        HttpResponse.json({ scenario_id: SCENARIO_ID, action_chips: [] }),
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
    renderEditor();

    const input = await screen.findByLabelText(/new action chip/i);
    await user.type(input, "Search the cairn{enter}");
    expect(screen.getByText("Search the cairn")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^save$/i }));

    expect(savedPayload).toEqual({ action_chips: ["Search the cairn"] });
  });

  it("does not add a duplicate chip (case-insensitive, trimmed)", async () => {
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}`, () =>
        HttpResponse.json({
          scenario_id: SCENARIO_ID,
          action_chips: ["Explore the ruins"],
        }),
      ),
    );

    const user = userEvent.setup();
    renderEditor();

    expect(await screen.findByText("Explore the ruins")).toBeInTheDocument();

    const input = screen.getByLabelText(/new action chip/i);
    await user.type(input, "  explore the ruins  {enter}");

    expect(screen.getAllByText("Explore the ruins")).toHaveLength(1);
    expect(input).toHaveValue("  explore the ruins  ");
  });
});
