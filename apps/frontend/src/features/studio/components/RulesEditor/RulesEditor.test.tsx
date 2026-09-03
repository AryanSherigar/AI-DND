import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
import { RulesEditor } from "./RulesEditor";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";

const renderEditor = (): void => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RulesEditor scenarioId={SCENARIO_ID} />
    </QueryClientProvider>,
  );
};

describe("RulesEditor", () => {
  it("edits and saves rules.text", async () => {
    let savedPayload: unknown = null;
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}`, () =>
        HttpResponse.json({ scenario_id: SCENARIO_ID, rules: { text: "" } }),
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

    const textarea = await screen.findByPlaceholderText(/hard world rules/i);
    await user.type(textarea, "No resurrection magic.");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    expect(savedPayload).toEqual({
      rules: { text: "No resurrection magic." },
    });
  });
});
