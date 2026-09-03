import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
import { EntityResponse } from "../../types/entity.types";
import { FactResponse } from "../../types/fact.types";
import { FactEditor } from "./FactEditor";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";

const buildEntity = (
  overrides: Partial<EntityResponse> = {},
): EntityResponse => ({
  entity_id: "entity-1",
  scenario_id: SCENARIO_ID,
  entity_type: "character",
  canonical_name: "The Warden",
  aliases: [],
  description: null,
  obtainable: null,
  attributes_schema: {},
  narrator_instruction: null,
  ...overrides,
});

const buildFact = (overrides: Partial<FactResponse> = {}): FactResponse => ({
  fact_id: "fact-1",
  scenario_id: SCENARIO_ID,
  subject_entity_id: "entity-1",
  predicate: "guards",
  object_entity_id: null,
  object_literal: "the gate",
  valid_from: null,
  when_active: null,
  hidden: false,
  superseded_fact_id: null,
  ...overrides,
});

const renderFactEditor = (): void => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <FactEditor scenarioId={SCENARIO_ID} />
    </QueryClientProvider>,
  );
};

const mockEntitiesAndFacts = (
  entities: EntityResponse[],
  facts: FactResponse[],
): void => {
  server.use(
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`, () =>
      HttpResponse.json({ items: entities }),
    ),
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/facts`, () =>
      HttpResponse.json({ items: facts }),
    ),
  );
};

describe("FactEditor", () => {
  it("clears the other object field when toggling object type, and blocks submit with neither set", async () => {
    const entity = buildEntity();
    mockEntitiesAndFacts([entity], []);
    let wasCreateCalled = false;
    server.use(
      http.post(`${API_URL}/v1/scenarios/${SCENARIO_ID}/facts`, () => {
        wasCreateCalled = true;
        return HttpResponse.json(buildFact());
      }),
    );

    const user = userEvent.setup();
    renderFactEditor();

    await user.click(await screen.findByRole("button", { name: /new fact/i }));
    await user.selectOptions(
      screen.getByLabelText(/^subject$/i),
      entity.entity_id,
    );

    const submitButton = screen.getByRole("button", { name: /^save$/i });
    expect(submitButton).toBeDisabled();
    expect(
      screen.getByText(/set either an object entity or a literal value/i),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^literal$/i }));
    await user.type(screen.getByLabelText(/object literal/i), "the gate");
    expect(screen.getByLabelText(/object literal/i)).toHaveValue("the gate");

    await user.click(screen.getByRole("button", { name: /^entity$/i }));
    expect(screen.getByLabelText(/object entity/i)).toHaveValue("");
    expect(submitButton).toBeDisabled();

    await user.selectOptions(
      screen.getByLabelText(/object entity/i),
      entity.entity_id,
    );
    await user.click(screen.getByRole("button", { name: /^literal$/i }));
    expect(screen.getByLabelText(/object literal/i)).toHaveValue("");

    expect(submitButton).toBeDisabled();
    await user.click(submitButton);
    expect(wasCreateCalled).toBe(false);
  });

  it("shows an inline warning when a fact references an entity that no longer exists", async () => {
    const fact = buildFact({ subject_entity_id: "missing-entity-id" });
    mockEntitiesAndFacts([], [fact]);

    renderFactEditor();

    expect(
      await screen.findByText(/subject: this entity no longer exists/i),
    ).toBeInTheDocument();
  });
});
