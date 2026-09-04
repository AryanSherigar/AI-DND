import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
import { useStudioStore } from "../../stores/studio.store";
import { EntityEditor } from "./EntityEditor";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";

const renderEntityEditor = (): void => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <EntityEditor scenarioId={SCENARIO_ID} />
    </QueryClientProvider>,
  );
};

describe("EntityEditor", () => {
  beforeEach(() => {
    useStudioStore.setState({
      factsEntityFilter: null,
      activeMasterTab: "entities",
    });
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entity-types`, () =>
        HttpResponse.json({ items: [] }),
      ),
    );
  });

  it("shows the obtainable toggle only when entity_type is item", async () => {
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`, () =>
        HttpResponse.json({ items: [] }),
      ),
    );
    const user = userEvent.setup();
    renderEntityEditor();

    await user.click(
      await screen.findByRole("button", { name: /new entity/i }),
    );

    const typeSelect = screen.getByLabelText(/entity type/i);
    expect(screen.queryByText(/obtainable/i)).not.toBeInTheDocument();

    await user.selectOptions(typeSelect, "item");
    expect(await screen.findByText(/obtainable/i)).toBeInTheDocument();

    await user.selectOptions(typeSelect, "character");
    await waitFor(() =>
      expect(screen.queryByText(/obtainable/i)).not.toBeInTheDocument(),
    );

    await user.selectOptions(typeSelect, "location");
    expect(screen.queryByText(/obtainable/i)).not.toBeInTheDocument();
  });

  it("expands a row to show full detail without opening the edit modal, and opens the edit modal only from the Edit button", async () => {
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`, () =>
        HttpResponse.json({
          items: [
            {
              entity_id: "entity-1",
              scenario_id: SCENARIO_ID,
              entity_type: "character",
              canonical_name: "The Warden",
              aliases: ["Warden"],
              description: "Guards the outer gate.",
              obtainable: null,
              attributes_schema: {
                loyalty: { type: "number", initial: 5 },
              },
              narrator_instruction: null,
              fact_count: 0,
            },
          ],
        }),
      ),
    );
    const user = userEvent.setup();
    renderEntityEditor();

    await screen.findByText("The Warden");
    expect(screen.queryByText(/aliases: warden/i)).not.toBeInTheDocument();

    await user.click(screen.getByText("The Warden"));
    expect(await screen.findByText(/aliases: warden/i)).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^edit$/i }));
    expect(await screen.findByPlaceholderText(/canonical name/i)).toHaveValue(
      "The Warden",
    );
  });

  it("jumps to the Facts tab filtered to this entity when 'View related facts' is clicked", async () => {
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`, () =>
        HttpResponse.json({
          items: [
            {
              entity_id: "entity-1",
              scenario_id: SCENARIO_ID,
              entity_type: "character",
              canonical_name: "The Warden",
              aliases: [],
              description: null,
              obtainable: null,
              attributes_schema: {},
              narrator_instruction: null,
              fact_count: 3,
            },
          ],
        }),
      ),
    );
    const user = userEvent.setup();
    renderEntityEditor();

    await user.click(await screen.findByText("The Warden"));
    await user.click(
      screen.getByRole("button", { name: /view 3 related facts/i }),
    );

    expect(useStudioStore.getState().activeMasterTab).toBe("facts");
    expect(useStudioStore.getState().factsEntityFilter).toBe("entity-1");
  });

  it("creates a custom entity type inline and uses it as the new entity's type", async () => {
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`, () =>
        HttpResponse.json({ items: [] }),
      ),
    );
    let createdTypePayload: unknown = null;
    let createdEntityPayload: unknown = null;
    server.use(
      http.post(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}/entity-types`,
        async ({ request }) => {
          createdTypePayload = await request.json();
          return HttpResponse.json(
            {
              scenario_entity_type_id: "type-1",
              scenario_id: SCENARIO_ID,
              type_key: "vehicle",
              display_label: "Vehicle",
              attributes_schema: {},
            },
            { status: 201 },
          );
        },
      ),
      http.post(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`,
        async ({ request }) => {
          createdEntityPayload = await request.json();
          return HttpResponse.json(
            {
              entity_id: "entity-1",
              scenario_id: SCENARIO_ID,
              entity_type: "vehicle",
              canonical_name: "The Skiff",
              aliases: [],
              description: null,
              obtainable: null,
              attributes_schema: {},
              narrator_instruction: null,
              fact_count: 0,
            },
            { status: 201 },
          );
        },
      ),
    );

    const user = userEvent.setup();
    renderEntityEditor();

    await user.click(
      await screen.findByRole("button", { name: /new entity/i }),
    );
    await user.selectOptions(
      screen.getByLabelText(/entity type/i),
      "__new_custom_type__",
    );
    await user.type(screen.getByLabelText(/custom type name/i), "Vehicle");
    await user.type(
      screen.getByPlaceholderText(/canonical name/i),
      "The Skiff",
    );
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() =>
      expect(createdTypePayload).toMatchObject({
        type_key: "vehicle",
        display_label: "Vehicle",
      }),
    );
    await waitFor(() =>
      expect(createdEntityPayload).toMatchObject({
        entity_type: "vehicle",
        canonical_name: "The Skiff",
      }),
    );
  });

  it("previews a type change and requires confirmation before applying it", async () => {
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`, () =>
        HttpResponse.json({
          items: [
            {
              entity_id: "entity-1",
              scenario_id: SCENARIO_ID,
              entity_type: "character",
              canonical_name: "The Warden",
              aliases: [],
              description: null,
              obtainable: null,
              attributes_schema: { health: { type: "number", initial: 150 } },
              narrator_instruction: null,
              fact_count: 0,
            },
          ],
        }),
      ),
      http.post(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}/entities/entity-1/type-change-preview`,
        () =>
          HttpResponse.json({
            dropped_fields: ["health"],
            retained_fields: [],
            added_fields: [],
          }),
      ),
    );

    const user = userEvent.setup();
    renderEntityEditor();

    await user.click(await screen.findByText("The Warden"));
    await user.click(screen.getByRole("button", { name: /^edit$/i }));

    await user.selectOptions(screen.getByLabelText(/entity type/i), "item");

    expect(await screen.findByText(/change type to item/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/entity type/i)).toHaveValue("character");

    await user.click(screen.getByRole("button", { name: /confirm change/i }));

    await waitFor(() =>
      expect(screen.getByLabelText(/entity type/i)).toHaveValue("item"),
    );
  });
});
