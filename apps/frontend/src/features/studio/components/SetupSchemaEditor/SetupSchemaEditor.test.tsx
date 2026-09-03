import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
import { SetupSchemaEditor } from "./SetupSchemaEditor";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";

const renderEditor = (): void => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <SetupSchemaEditor scenarioId={SCENARIO_ID} />
    </QueryClientProvider>,
  );
};

describe("SetupSchemaEditor", () => {
  it("adds an archetype with a parsed value and saves the expected shape", async () => {
    let savedPayload: unknown = null;
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}`, () =>
        HttpResponse.json({ scenario_id: SCENARIO_ID, setup_archetypes: [] }),
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

    await user.click(
      await screen.findByRole("button", { name: /add archetype/i }),
    );
    await user.type(
      screen.getByLabelText(/archetype name/i),
      "Warrior",
    );
    await user.type(screen.getByLabelText(/value key/i), "player.health");
    await user.type(screen.getByLabelText(/value data/i), "100");
    await user.click(screen.getByRole("button", { name: /^add$/i }));

    await user.click(screen.getByRole("button", { name: /^save$/i }));

    const payload = savedPayload as {
      setup_archetypes: { name: string; values: Record<string, unknown> }[];
    };
    expect(payload.setup_archetypes).toHaveLength(1);
    expect(payload.setup_archetypes[0].name).toBe("Warrior");
    expect(payload.setup_archetypes[0].values).toEqual({
      "player.health": 100,
    });
  });
});
