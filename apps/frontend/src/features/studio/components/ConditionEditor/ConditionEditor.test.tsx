import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
import { ScenarioResponse } from "../../types/scenario.types";
import { ConditionEditor } from "./ConditionEditor";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";

const buildScenario = (
  overrides: Partial<ScenarioResponse> = {},
): ScenarioResponse => ({
  scenario_id: SCENARIO_ID,
  creator_id: "creator-1",
  creator_display_name: null,
  is_bookmarked: false,
  can_review: false,
  title: "The Hollow Cairn",
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
  rating_avg: "0",
  narrator_persona: null,
  world_data: {},
  setup_schema: [],
  state_schema: {
    player: {
      type: "object",
      fields: {
        sanity: { type: "number", label: "Sanity" },
      },
    },
    flags: {
      type: "object",
      fields: {
        entered_cairn: { type: "boolean", label: "Entered the Cairn" },
      },
    },
  },
  end_conditions: [],
  checkpoints: [],
  rules: {},
  opening_scene: null,
  narration_font: null,
  action_chips: [],
  setup_archetypes: [],
  current_version: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  ...overrides,
});

const renderConditionEditor = (): void => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ConditionEditor scenarioId={SCENARIO_ID} />
    </QueryClientProvider>,
  );
};

const mockBaseHandlers = (): void => {
  server.use(
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}`, () =>
      HttpResponse.json(buildScenario()),
    ),
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`, () =>
      HttpResponse.json({ items: [] }),
    ),
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/conditions`, () =>
      HttpResponse.json({ items: [] }),
    ),
  );
};

describe("ConditionEditor", () => {
  it("builds a ConditionCreate payload with a state_mutation (Effect C)", async () => {
    mockBaseHandlers();
    let capturedPayload: Record<string, unknown> | null = null;
    server.use(
      http.post(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}/conditions`,
        async ({ request }) => {
          capturedPayload = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({
            condition_id: "condition-1",
            scenario_id: SCENARIO_ID,
            ...capturedPayload,
            condition_version: "1",
            metadata: {},
          });
        },
      ),
    );

    const user = userEvent.setup();
    renderConditionEditor();

    await user.click(
      await screen.findByRole("button", { name: /new condition/i }),
    );

    await user.type(screen.getByPlaceholderText(/^label$/i), "Entered the cairn");
    await user.type(
      screen.getByPlaceholderText(/narrator instruction/i),
      "Sanity drops as the cairn closes in.",
    );

    const fieldInput = screen.getByPlaceholderText("player.health");
    await user.type(fieldInput, "flags.entered_cairn");

    const valueSelect = screen.getAllByRole("combobox")[2];
    await user.selectOptions(valueSelect, "true");

    await user.click(
      screen.getByLabelText(/has state mutation \(effect c\)/i),
    );
    await user.type(screen.getByLabelText(/mutation path/i), "player.sanity");
    await user.selectOptions(
      screen.getByLabelText(/mutation operation/i),
      "decrement",
    );
    await user.type(screen.getByLabelText(/mutation value/i), "2");

    await user.click(screen.getByRole("button", { name: /^save$/i }));

    expect(capturedPayload).toMatchObject({
      label: "Entered the cairn",
      narrator_instruction: "Sanity drops as the cairn closes in.",
      condition_expression: {
        field: "flags.entered_cairn",
        op: "==",
        value: true,
      },
      state_mutation: {
        path: "player.sanity",
        op: "decrement",
        value: "2",
      },
    });
  });
});
