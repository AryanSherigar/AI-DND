import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
import { MasterModeStudioLayout } from "../../Layout/MasterModeStudioLayout";
import { StudioDocumentLayout } from "../../Layout/StudioDocumentLayout";
import { useStudioStore } from "../../../stores/studio.store";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";

// jsdom has no IntersectionObserver; StudioDocumentLayout's scroll-spy
// effect needs a stub so mounting it in this test doesn't throw.
class IntersectionObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
(global as unknown as { IntersectionObserver: unknown }).IntersectionObserver =
  IntersectionObserverStub;

describe("Minigames tab", () => {
  it("appears in MasterModeStudioLayout and renders MinigameEditor when selected", async () => {
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}`, () =>
        HttpResponse.json({ scenario_id: SCENARIO_ID, state_schema: {} }),
      ),
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`, () =>
        HttpResponse.json({ items: [] }),
      ),
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/minigames`, () =>
        HttpResponse.json({ items: [] }),
      ),
    );
    useStudioStore.setState({ activeMasterTab: "minigames" });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <MasterModeStudioLayout scenarioId={SCENARIO_ID} />
        </QueryClientProvider>
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("button", { name: /^minigames$/i }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: /^minigames$/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /new minigame/i }),
    ).toBeInTheDocument();
  });

  it("is never present in StudioDocumentLayout (newbie-mode surface)", () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <StudioDocumentLayout />
        </QueryClientProvider>
      </MemoryRouter>,
    );

    expect(
      screen.queryByRole("button", { name: /^minigames$/i }),
    ).not.toBeInTheDocument();
  });
});
