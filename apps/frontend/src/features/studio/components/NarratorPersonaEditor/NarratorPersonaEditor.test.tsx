import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
import { NarratorPersonaEditor } from "./NarratorPersonaEditor";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";

const renderEditor = (): void => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <NarratorPersonaEditor scenarioId={SCENARIO_ID} />
    </QueryClientProvider>,
  );
};

describe("NarratorPersonaEditor", () => {
  it("adds a checkpoint override and saves it under checkpoints", async () => {
    let savedPayload: unknown = null;
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}`, () =>
        HttpResponse.json({ scenario_id: SCENARIO_ID, checkpoints: [] }),
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
      await screen.findByRole("button", { name: /add checkpoint/i }),
    );
    await user.type(
      screen.getByLabelText(/trigger description/i),
      "Entering the cairn",
    );
    await user.type(
      screen.getByLabelText(/persona override/i),
      "Grim and foreboding",
    );

    await user.click(screen.getByRole("button", { name: /^save$/i }));

    const payload = savedPayload as {
      checkpoints: {
        trigger_description: string;
        persona_override: string;
      }[];
    };
    expect(payload.checkpoints).toHaveLength(1);
    expect(payload.checkpoints[0].trigger_description).toBe(
      "Entering the cairn",
    );
    expect(payload.checkpoints[0].persona_override).toBe(
      "Grim and foreboding",
    );
  });
});
