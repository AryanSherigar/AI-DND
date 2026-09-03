import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
import { NarrationFontPicker } from "./NarrationFontPicker";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";

const renderPicker = (): void => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <NarrationFontPicker scenarioId={SCENARIO_ID} />
    </QueryClientProvider>,
  );
};

describe("NarrationFontPicker", () => {
  it("saves immediately when a new font is selected", async () => {
    let savedPayload: unknown = null;
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}`, () =>
        HttpResponse.json({
          scenario_id: SCENARIO_ID,
          narration_font: "serif",
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
    renderPicker();

    const select = await screen.findByLabelText(/narration font/i);
    await user.selectOptions(select, "monospace");

    expect(savedPayload).toEqual({ narration_font: "monospace" });
  });
});
