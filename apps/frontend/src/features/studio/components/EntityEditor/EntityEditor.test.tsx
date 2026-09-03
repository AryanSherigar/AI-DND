import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
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
});
