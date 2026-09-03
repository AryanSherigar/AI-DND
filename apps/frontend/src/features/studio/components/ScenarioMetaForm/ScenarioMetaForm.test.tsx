import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
import { ScenarioMetaForm } from "./ScenarioMetaForm";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";

const renderForm = (): void => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ScenarioMetaForm scenarioId={SCENARIO_ID} />
    </QueryClientProvider>,
  );
};

describe("ScenarioMetaForm", () => {
  it("edits the title and saves the updated metadata", async () => {
    let savedPayload: unknown = null;
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}`, () =>
        HttpResponse.json({
          scenario_id: SCENARIO_ID,
          title: "The Hollow Cairn",
          logline: "A dungeon of forgotten kings.",
          genre_tags: [],
          complexity_tier: "master",
          content_tag: "teen",
          player_count_support: "solo",
        }),
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
    renderForm();

    const titleInput = await screen.findByDisplayValue("The Hollow Cairn");
    await user.clear(titleInput);
    await user.type(titleInput, "The Deeper Cairn");

    await user.click(screen.getByRole("button", { name: /^save$/i }));

    const payload = savedPayload as { title: string };
    expect(payload.title).toBe("The Deeper Cairn");
  });
});
