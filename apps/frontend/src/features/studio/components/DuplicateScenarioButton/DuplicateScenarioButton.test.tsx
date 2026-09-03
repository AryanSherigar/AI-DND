import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
import { DuplicateScenarioButton } from "./DuplicateScenarioButton";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";
const NEW_SCENARIO_ID = "scenario-2";

const buildScenarioResponse = (scenarioId: string) => ({
  scenario_id: scenarioId,
  creator_id: "user-1",
  creator_display_name: "Dev Creator",
  is_bookmarked: false,
  can_review: false,
  title: "The Hollow Cairn (Copy)",
  logline: null,
  mode: "master",
  status: "draft",
  genre_tags: [],
  complexity_tier: "master",
  player_count_support: "solo",
  estimated_playtime: null,
  cover_image_url: null,
  content_tag: null,
  publish_error: null,
  published_at: null,
  play_count: 0,
  rating_avg: "0.00",
  narrator_persona: null,
  world_data: {},
  setup_schema: [],
  state_schema: {},
  end_conditions: [],
  checkpoints: [],
  rules: {},
  opening_scene: null,
  narration_font: null,
  action_chips: [],
  setup_archetypes: [],
  current_version: 1,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
});

const renderDuplicateButton = (): void => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/studio/${SCENARIO_ID}/edit`]}>
        <Routes>
          <Route
            path={`/studio/${SCENARIO_ID}/edit`}
            element={<DuplicateScenarioButton scenarioId={SCENARIO_ID} />}
          />
          <Route
            path={`/studio/${NEW_SCENARIO_ID}/edit`}
            element={
              <div data-testid="new-scenario-edit-route">
                New scenario edit page
              </div>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe("DuplicateScenarioButton", () => {
  it("duplicates the scenario and navigates to the new scenario's edit route", async () => {
    server.use(
      http.post(`${API_URL}/v1/scenarios/${SCENARIO_ID}/duplicate`, () =>
        HttpResponse.json(buildScenarioResponse(NEW_SCENARIO_ID), {
          status: 201,
        }),
      ),
    );

    renderDuplicateButton();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /duplicate/i }));

    await waitFor(() => {
      expect(screen.getByTestId("new-scenario-edit-route")).toBeInTheDocument();
    });
  });

  it("shows an inline error when duplication fails", async () => {
    server.use(
      http.post(`${API_URL}/v1/scenarios/${SCENARIO_ID}/duplicate`, () =>
        HttpResponse.json(
          { detail: "Access denied for this scenario" },
          { status: 403 },
        ),
      ),
    );

    renderDuplicateButton();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /duplicate/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Access denied for this scenario"),
      ).toBeInTheDocument();
    });
  });
});
