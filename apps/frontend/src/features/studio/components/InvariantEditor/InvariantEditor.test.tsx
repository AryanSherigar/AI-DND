import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
import { ScenarioResponse } from "../../types/scenario.types";
import { InvariantEditor } from "./InvariantEditor";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";
const __dirname = path.dirname(fileURLToPath(import.meta.url));

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
        health: { type: "number", label: "Health" },
        max_health: { type: "number", label: "Max Health" },
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

const renderInvariantEditor = (): void => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <InvariantEditor scenarioId={SCENARIO_ID} />
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
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/invariants`, () =>
      HttpResponse.json({ items: [] }),
    ),
  );
};

describe("InvariantEditor", () => {
  it("builds an InvariantCreate payload from the form", async () => {
    mockBaseHandlers();
    let capturedPayload: Record<string, unknown> | null = null;
    server.use(
      http.post(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}/invariants`,
        async ({ request }) => {
          capturedPayload = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({
            invariant_id: "invariant-1",
            scenario_id: SCENARIO_ID,
            ...capturedPayload,
          });
        },
      ),
    );

    const user = userEvent.setup();
    renderInvariantEditor();

    await user.click(
      await screen.findByRole("button", { name: /new invariant/i }),
    );

    await user.type(
      screen.getByPlaceholderText(/^label$/i),
      "Health never exceeds max",
    );
    await user.selectOptions(screen.getByLabelText(/applies to/i), "player");
    await user.type(
      screen.getByPlaceholderText(/narrator text/i),
      "The Warden's wounds cannot exceed their vitality.",
    );

    const fieldInput = screen.getByPlaceholderText("player.health");
    await user.type(fieldInput, "player.health");

    const operatorSelect = screen.getAllByRole("combobox")[2];
    await user.selectOptions(operatorSelect, "<=");

    const valueInput = screen.getByRole("spinbutton");
    await user.type(valueInput, "100");

    await user.click(screen.getByRole("button", { name: /^save$/i }));

    expect(capturedPayload).toMatchObject({
      label: "Health never exceeds max",
      applies_to: "player",
      narrator_text: "The Warden's wounds cannot exceed their vitality.",
      invariant_expression: {
        field: "player.health",
        op: "<=",
        value: 100,
      },
    });
  });

  it("imports the shared ExpressionBuilder instead of reimplementing expression UI", () => {
    const source = readFileSync(
      path.join(__dirname, "InvariantForm.tsx"),
      "utf-8",
    );

    expect(source).toContain(
      'import { ExpressionBuilder } from "../ConditionEditor/ExpressionBuilder/ExpressionBuilder"',
    );
    expect(source).not.toMatch(/FieldPicker|OperatorPicker|ValueInput/);
  });
});
