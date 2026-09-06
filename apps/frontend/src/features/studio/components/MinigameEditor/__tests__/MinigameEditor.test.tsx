import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/test/msw/server";
import { MinigameEditor } from "../MinigameEditor";

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";

const mockBaseHandlers = (): void => {
  server.use(
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}`, () =>
      HttpResponse.json({
        scenario_id: SCENARIO_ID,
        state_schema: {
          player: {
            type: "object",
            fields: { health: { type: "number", label: "Health" } },
          },
        },
      }),
    ),
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`, () =>
      HttpResponse.json({ items: [] }),
    ),
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/minigames`, () =>
      HttpResponse.json({ items: [] }),
    ),
  );
};

const renderMinigameEditor = (): void => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MinigameEditor scenarioId={SCENARIO_ID} />
    </QueryClientProvider>,
  );
};

const openCreateForm = async (
  user: ReturnType<typeof userEvent.setup>,
): Promise<void> => {
  await user.click(
    await screen.findByRole("button", { name: /new minigame/i }),
  );
};

describe("MinigameEditor form conditional sections", () => {
  it("shows the dodge difficulty slider by default and swaps to the Replit URL field on type change", async () => {
    mockBaseHandlers();
    const user = userEvent.setup();
    renderMinigameEditor();
    await openCreateForm(user);

    expect(screen.getByLabelText(/dodge difficulty/i)).toBeInTheDocument();
    expect(
      screen.queryByPlaceholderText(/your-repl\.replit\.app/i),
    ).not.toBeInTheDocument();

    await user.selectOptions(
      screen.getByLabelText(/minigame type/i),
      "replit_embed",
    );

    expect(
      screen.queryByLabelText(/dodge difficulty/i),
    ).not.toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/your-repl\.replit\.app/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /test connection/i }),
    ).toBeInTheDocument();
  });

  it("shows binary win/lose fields by default and swaps to tiered score ranges", async () => {
    mockBaseHandlers();
    const user = userEvent.setup();
    renderMinigameEditor();
    await openCreateForm(user);

    expect(screen.getByText(/^on win$/i)).toBeInTheDocument();
    expect(screen.getByText(/^on lose$/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /add score range/i }),
    ).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText(/outcome mode/i), "tiered");

    expect(screen.queryByText(/^on win$/i)).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /add score range/i }),
    ).toBeInTheDocument();
  });

  it("always shows the timeout mutation fields regardless of outcome mode", async () => {
    mockBaseHandlers();
    const user = userEvent.setup();
    renderMinigameEditor();
    await openCreateForm(user);

    expect(
      screen.getByText(/on connection failure \/ timeout/i),
    ).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText(/outcome mode/i), "tiered");

    expect(
      screen.getByText(/on connection failure \/ timeout/i),
    ).toBeInTheDocument();
  });
});

describe("MinigameEditor create flow", () => {
  it("builds a MinigameCreate payload for a dodge/binary minigame and calls the create mutation", async () => {
    mockBaseHandlers();
    let capturedPayload: Record<string, unknown> | null = null;
    server.use(
      http.post(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}/minigames`,
        async ({ request }) => {
          capturedPayload = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({
            minigame_id: "minigame-1",
            scenario_id: SCENARIO_ID,
            ...capturedPayload,
          });
        },
      ),
    );

    const user = userEvent.setup();
    renderMinigameEditor();
    await openCreateForm(user);

    await user.type(screen.getByLabelText(/^label$/i), "Warden's Onslaught");

    const fieldInput = screen.getByPlaceholderText("player.health");
    await user.type(fieldInput, "player.health");

    // Three mutation rows are always rendered (win, lose, timeout — none are
    // optional in a minigame form per StateMutationFields isOptional={false}).
    const pathInputs = screen.getAllByLabelText(/mutation path/i);
    await user.type(pathInputs[0], "player.ember_charm");
    await user.type(pathInputs[1], "player.health");

    const valueInputs = screen.getAllByLabelText(/mutation value/i);
    await user.type(valueInputs[0], "true");
    await user.type(valueInputs[1], "-15");

    await user.click(screen.getByRole("button", { name: /^save$/i }));

    expect(capturedPayload).toMatchObject({
      label: "Warden's Onslaught",
      minigame_type: "dodge",
      outcome_mode: "binary",
      dodge_config: { difficulty: 3 },
      replit_embed_url: null,
      win_mutation: { path: "player.ember_charm", op: "set", value: "true" },
      lose_mutation: { path: "player.health", op: "set", value: "-15" },
    });
  });
});
