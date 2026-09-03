import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
import { OpeningSceneEditor } from "./OpeningSceneEditor";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";

const renderEditor = (): void => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <OpeningSceneEditor scenarioId={SCENARIO_ID} />
    </QueryClientProvider>,
  );
};

describe("OpeningSceneEditor", () => {
  it("edits and saves the opening scene text", async () => {
    let savedPayload: unknown = null;
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}`, () =>
        HttpResponse.json({ scenario_id: SCENARIO_ID, opening_scene: "" }),
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

    const textarea = await screen.findByPlaceholderText(
      /describe the scene/i,
    );
    await user.type(textarea, "You wake in a cold, stone cairn.");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    expect(savedPayload).toEqual({
      opening_scene: "You wake in a cold, stone cairn.",
    });
  });
});
