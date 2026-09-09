import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
import { useStudioStore } from "../../stores/studio.store";
import { MasterModeStudioLayout } from "./MasterModeStudioLayout";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";

const renderLayout = (): void => {
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
};

describe("MasterModeStudioLayout", () => {
  beforeEach(() => {
    useStudioStore.setState({
      activeMasterTab: "entities",
    });
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}`, () =>
        HttpResponse.json({
          scenario_id: SCENARIO_ID,
          title: "The Ancient Keep",
          logline: "An old castle.",
          genre_tags: [],
          complexity_tier: "master",
          content_tag: "teen",
          player_count_support: "solo",
          cover_image_url: null,
          opening_scene: "Thunder rumbles outside.",
          rules: { text: "No magic" },
        }),
      ),
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`, () =>
        HttpResponse.json({ items: [] }),
      ),
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entity-types`, () =>
        HttpResponse.json({ items: [] }),
      ),
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/music`, () =>
        HttpResponse.json({ items: [] }),
      ),
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/music/quota`, () =>
        HttpResponse.json({
          scenario_generations_used: 0,
          scenario_generations_limit: 20,
          creator_generations_used_today: 0,
          creator_generations_limit_per_day: 10,
        }),
      ),
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/assistant/chat`, () =>
        HttpResponse.json({ messages: [] }),
      ),
    );
  });

  it("renders the active tab and keeps visited tabs mounted when switching sections", async () => {
    const user = userEvent.setup();
    renderLayout();

    // Initially on "entities"
    expect(
      await screen.findByRole("button", { name: /new entity/i }),
    ).toBeInTheDocument();

    // Click "Mood Music" section
    const musicNavButton = screen.getByRole("button", {
      name: /^mood music$/i,
    });
    await user.click(musicNavButton);

    // Music slot editor is visible
    expect(
      await screen.findByRole("heading", { name: /^mood music$/i }),
    ).toBeInTheDocument();

    // Entities panel is still mounted in the DOM, but hidden
    const newEntityButton = screen.getByRole("button", { name: /new entity/i });
    expect(newEntityButton).toBeInTheDocument();
    expect(newEntityButton.closest(".hidden")).not.toBeNull();

    // Click "Setup & Narrator" section
    const setupNavButton = screen.getByRole("button", {
      name: /^setup & narrator$/i,
    });
    await user.click(setupNavButton);

    // Setup panel is visible
    expect(
      await screen.findByDisplayValue("The Ancient Keep"),
    ).toBeInTheDocument();

    // All visited panels (entities, music, setup) remain in the DOM
    expect(newEntityButton).toBeInTheDocument();
    expect(screen.getByText("Peaceful")).toBeInTheDocument();
  });
});
