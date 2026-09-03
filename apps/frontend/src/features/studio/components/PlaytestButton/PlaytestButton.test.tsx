import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
import { PlaytestButton } from "./PlaytestButton";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";
const PLAYTHROUGH_ID = "playthrough-1";

const renderPlaytestButton = (): void => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/studio/${SCENARIO_ID}/edit`]}>
        <Routes>
          <Route
            path="/studio/:id/edit"
            element={<PlaytestButton scenarioId={SCENARIO_ID} />}
          />
          <Route
            path="/play/:id"
            element={<div data-testid="play-route">Playing</div>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe("PlaytestButton", () => {
  it("starts a playtest and navigates to the returned playthrough's play route", async () => {
    server.use(
      http.post(`${API_URL}/v1/scenarios/${SCENARIO_ID}/playtest`, () =>
        HttpResponse.json(
          {
            playthrough_id: PLAYTHROUGH_ID,
            scenario_id: SCENARIO_ID,
            scenario_title: "The Hollow Cairn",
            created_by: "user-1",
            state: {},
            checkpoint: null,
            turn_count: 0,
            status: "active",
            is_playtest: true,
            scenario_version: 1,
            scenario_snapshot: {},
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            participant_id: "participant-1",
          },
          { status: 201 },
        ),
      ),
    );

    renderPlaytestButton();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /playtest/i }));

    await waitFor(() => {
      expect(screen.getByTestId("play-route")).toBeInTheDocument();
    });
  });

  it("shows an inline error when the playtest request fails", async () => {
    server.use(
      http.post(`${API_URL}/v1/scenarios/${SCENARIO_ID}/playtest`, () =>
        HttpResponse.json(
          { detail: "Access denied for this scenario" },
          { status: 403 },
        ),
      ),
    );

    renderPlaytestButton();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /playtest/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Access denied for this scenario"),
      ).toBeInTheDocument();
    });
  });
});
