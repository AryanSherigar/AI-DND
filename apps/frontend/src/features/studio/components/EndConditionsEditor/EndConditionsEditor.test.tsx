import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { renderHook } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import React from "react";
import { describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
import { EndConditionResponse } from "../../types/end_condition.types";
import { useEndConditions } from "../../hooks/useEndConditions";
import { EndConditionsEditor } from "./EndConditionsEditor";
import { buildReorderedIds } from "./endConditionOrdering";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";

const buildEndCondition = (
  overrides: Partial<EndConditionResponse> = {},
): EndConditionResponse => ({
  end_condition_id: "end-1",
  scenario_id: SCENARIO_ID,
  condition_expression: { field: "player.health", op: "<=", value: 0 },
  outcome_tag: "lose",
  outcome_title: "Defeated",
  outcome_text: "You fall.",
  is_secret: false,
  priority: 0,
  ...overrides,
});

const mockScenarioAndEntities = (): void => {
  server.use(
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}`, () =>
      HttpResponse.json({
        scenario_id: SCENARIO_ID,
        state_schema: {},
      }),
    ),
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`, () =>
      HttpResponse.json({ items: [] }),
    ),
  );
};

describe("buildReorderedIds", () => {
  it("reorders ids so the dragged item moves to the target position", () => {
    const first = buildEndCondition({ end_condition_id: "a", priority: 0 });
    const second = buildEndCondition({ end_condition_id: "b", priority: 1 });

    const result = buildReorderedIds([first, second], "b", "a");

    expect(result).toEqual(["b", "a"]);
  });
});

describe("EndConditionsEditor", () => {
  it("calls the reorder mutation with the new ordered ids and re-renders the list optimistically before the network resolves", async () => {
    mockScenarioAndEntities();
    const first = buildEndCondition({
      end_condition_id: "a",
      priority: 0,
      outcome_title: "Alpha",
    });
    const second = buildEndCondition({
      end_condition_id: "b",
      priority: 1,
      outcome_title: "Beta",
    });
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/end_conditions`, () =>
        HttpResponse.json({ items: [first, second] }),
      ),
    );

    let receivedBody: unknown = null;
    server.use(
      http.post(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}/end_conditions/reorder`,
        async ({ request }) => {
          receivedBody = await request.json();
          await delay("infinite");
          return HttpResponse.json({ items: [] });
        },
      ),
    );

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    render(
      <QueryClientProvider client={queryClient}>
        <EndConditionsEditor scenarioId={SCENARIO_ID} />
      </QueryClientProvider>,
    );

    await screen.findByTestId("end-condition-row-a");

    const { result } = renderHook(() => useEndConditions(SCENARIO_ID), {
      wrapper,
    });

    await waitFor(() => expect(result.current.endConditions).toHaveLength(2));

    result.current.reorderEndConditions(["b", "a"]);

    await waitFor(() => {
      const rows = screen.getAllByText(/^(Alpha|Beta)$/);
      expect(rows[0]).toHaveTextContent("Beta");
      expect(rows[1]).toHaveTextContent("Alpha");
    });

    await waitFor(() => {
      expect(receivedBody).toEqual({ ordered_end_condition_ids: ["b", "a"] });
    });
  });

  it("opens the edit modal prefilled and calls update (not create) on submit", async () => {
    mockScenarioAndEntities();
    const endCondition = buildEndCondition();
    server.use(
      http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/end_conditions`, () =>
        HttpResponse.json({ items: [endCondition] }),
      ),
    );

    let receivedBody: unknown = null;
    let wasCreateCalled = false;
    server.use(
      http.patch(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}/end_conditions/${endCondition.end_condition_id}`,
        async ({ request }) => {
          receivedBody = await request.json();
          return HttpResponse.json({
            ...endCondition,
            outcome_title: "Vanquished",
          });
        },
      ),
      http.post(`${API_URL}/v1/scenarios/${SCENARIO_ID}/end_conditions`, () => {
        wasCreateCalled = true;
        return HttpResponse.json(endCondition);
      }),
    );

    const user = userEvent.setup();
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <EndConditionsEditor scenarioId={SCENARIO_ID} />
      </QueryClientProvider>,
    );

    await user.click(await screen.findByRole("button", { name: /^edit$/i }));

    const titleInput = screen.getByLabelText(/outcome title/i);
    expect(titleInput).toHaveValue(endCondition.outcome_title);

    await user.clear(titleInput);
    await user.type(titleInput, "Vanquished");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() =>
      expect(receivedBody).toMatchObject({ outcome_title: "Vanquished" }),
    );
    expect(wasCreateCalled).toBe(false);
  });
});
