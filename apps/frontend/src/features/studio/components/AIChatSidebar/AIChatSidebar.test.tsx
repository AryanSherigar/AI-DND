import type { ComponentProps } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "@/test/msw/server";
import { SSEHandlers } from "@/shared/lib/sse-client";
import { useAuthStore } from "@/features/auth/stores/auth.store";
import { useStudioStore } from "../../stores/studio.store";
import { AIChatSidebar } from "./AIChatSidebar";

let capturedSSEHandlers: SSEHandlers | null = null;

vi.mock("@/shared/lib/sse-client", () => ({
  createPostSSEConnection: (
    _url: string,
    _body: unknown,
    _token: string | null,
    handlers: SSEHandlers,
  ) => {
    capturedSSEHandlers = handlers;
    return vi.fn();
  },
}));

const renderChatSidebar = (props: ComponentProps<typeof AIChatSidebar>) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AIChatSidebar {...props} />
    </QueryClientProvider>,
  );
};

const API_URL = "http://localhost:8000";
const SCENARIO_ID = "scenario-1";
const USER_ID = "user-1";

const seedMasterMessage = (content: string) => {
  localStorage.setItem(
    `aidnd_studio_assistant_chat:master:${USER_ID}:${SCENARIO_ID}`,
    JSON.stringify([
      { id: "msg-1", role: "assistant", content, timestamp: Date.now() },
    ]),
  );
};

const mockMasterScenarioReads = () => {
  server.use(
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`, () =>
      HttpResponse.json({ items: [] }),
    ),
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/facts`, () =>
      HttpResponse.json({ items: [] }),
    ),
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/conditions`, () =>
      HttpResponse.json({ items: [] }),
    ),
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/invariants`, () =>
      HttpResponse.json({ items: [] }),
    ),
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}/end_conditions`, () =>
      HttpResponse.json({ items: [] }),
    ),
    http.get(`${API_URL}/v1/scenarios/${SCENARIO_ID}`, () =>
      HttpResponse.json({
        scenario_id: SCENARIO_ID,
        title: "Sunken Kingdom",
        mode: "master",
        state_schema: { gold: { type: "number" } },
      }),
    ),
  );
};

describe("AIChatSidebar", () => {
  beforeEach(() => {
    localStorage.clear();
    useStudioStore.getState().resetDraft();
    useAuthStore.setState({
      user: { user_id: USER_ID, display_name: "Test Creator" },
      accessToken: "test-token",
      isAuthenticated: true,
    });
  });

  afterEach(() => {
    useAuthStore.setState({
      user: null,
      accessToken: null,
      isAuthenticated: false,
    });
  });

  it("renders default welcome message and dynamic prompt chips", () => {
    renderChatSidebar({ activeSection: "meta" });

    expect(screen.getByText(/Greetings, creator/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: /\+ Suggest 3 catchy scenario titles/i,
      }),
    ).toBeInTheDocument();
  });

  it("switches prompt chips when activeSection changes", () => {
    const queryClient = new QueryClient();
    const { rerender } = render(
      <QueryClientProvider client={queryClient}>
        <AIChatSidebar activeSection="meta" />
      </QueryClientProvider>,
    );
    expect(
      screen.getByRole("button", {
        name: /\+ Suggest 3 catchy scenario titles/i,
      }),
    ).toBeInTheDocument();

    rerender(
      <QueryClientProvider client={queryClient}>
        <AIChatSidebar activeSection="lore" />
      </QueryClientProvider>,
    );
    expect(
      screen.getByRole("button", { name: /\+ Brainstorm 3 unique factions/i }),
    ).toBeInTheDocument();
  });

  it("applies an action card to draft when empty", async () => {
    const user = userEvent.setup();
    const messagesWithAction = [
      {
        id: "msg-action",
        role: "assistant",
        content:
          "Here is a conflict:\n```action:conflict\nThe Blood Moon awakens the ancient Colossus.\n```",
        timestamp: Date.now(),
      },
    ];
    localStorage.setItem(
      `aidnd_studio_assistant_chat:newbie:${USER_ID}:draft`,
      JSON.stringify(messagesWithAction),
    );

    renderChatSidebar({ activeSection: "lore" });

    const applyButton = screen.getByRole("button", {
      name: /Apply to Main Conflict \/ Goal/i,
    });
    expect(applyButton).toBeInTheDocument();

    await user.click(applyButton);

    await waitFor(() => {
      expect(useStudioStore.getState().newbieDraft.mainConflict).toBe(
        "The Blood Moon awakens the ancient Colossus.",
      );
      expect(useStudioStore.getState().newbieDraft.includeConflict).toBe(true);
    });
  });

  it("opens ConflictModal when target field already has content and allows append", async () => {
    const user = userEvent.setup();
    useStudioStore.getState().updateNewbieDraft({
      mainConflict: "Existing initial conflict.",
    });

    const messagesWithAction = [
      {
        id: "msg-action-2",
        role: "assistant",
        content:
          "Additional conflict:\n```action:conflict\nSecondary dark rift opens.\n```",
        timestamp: Date.now(),
      },
    ];
    localStorage.setItem(
      `aidnd_studio_assistant_chat:newbie:${USER_ID}:draft`,
      JSON.stringify(messagesWithAction),
    );

    renderChatSidebar({ activeSection: "lore" });

    const applyButton = screen.getByRole("button", {
      name: /Apply to Main Conflict \/ Goal/i,
    });
    await user.click(applyButton);

    expect(screen.getByText("Field Conflict Detected")).toBeInTheDocument();
    expect(screen.getByText("Existing initial conflict.")).toBeInTheDocument();
    expect(screen.getAllByText("Secondary dark rift opens.")).toHaveLength(2);

    await user.click(screen.getByRole("button", { name: /Append to End/i }));

    await waitFor(() => {
      expect(useStudioStore.getState().newbieDraft.mainConflict).toBe(
        "Existing initial conflict.\n\nSecondary dark rift opens.",
      );
    });
  });

  it("updates Step1Meta input on screen when 'Apply to Scenario Title' is clicked", async () => {
    const user = userEvent.setup();
    const messagesWithTitleAction = [
      {
        id: "msg-title-action",
        role: "assistant",
        content:
          "Here is a title:\n```action:title\nMud, Blood, and Three Banners\n```",
        timestamp: Date.now(),
      },
    ];
    localStorage.setItem(
      `aidnd_studio_assistant_chat:newbie:${USER_ID}:draft`,
      JSON.stringify(messagesWithTitleAction),
    );

    const { Step1Meta } = await import("../NewbieWizard/Step1Meta");
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <div>
          <Step1Meta />
          <AIChatSidebar activeSection="meta" />
        </div>
      </QueryClientProvider>,
    );

    const input = screen.getByPlaceholderText(
      "e.g., The Whispering Caverns",
    ) as HTMLInputElement;
    expect(input.value).toBe("");

    const applyButton = screen.getByRole("button", {
      name: /Apply to Scenario Title/i,
    });
    await user.click(applyButton);

    await waitFor(() => {
      expect(input.value).toBe("Mud, Blood, and Three Banners");
    });
  });
});

describe("AIChatSidebar - master mode", () => {
  beforeEach(() => {
    localStorage.clear();
    useStudioStore.setState({ mode: "master" });
    useAuthStore.setState({
      user: { user_id: USER_ID, display_name: "Test Creator" },
      accessToken: "test-token",
      isAuthenticated: true,
    });
    mockMasterScenarioReads();
  });

  afterEach(() => {
    useStudioStore.setState({ mode: "newbie" });
    useAuthStore.setState({
      user: null,
      accessToken: null,
      isAuthenticated: false,
    });
    capturedSSEHandlers = null;
  });

  it("creates an entity via Apply, hitting the real core-api endpoint", async () => {
    let createdPayload: unknown = null;
    server.use(
      http.post(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`,
        async ({ request }) => {
          createdPayload = await request.json();
          return HttpResponse.json(
            {
              entity_id: "entity-1",
              scenario_id: SCENARIO_ID,
              ...(createdPayload as Record<string, unknown>),
            },
            { status: 201 },
          );
        },
      ),
    );
    seedMasterMessage(
      'Here is a villain:\n```action:entity {"temp_id":"villain"}\n{"entity_type":"character","canonical_name":"The Warden"}\n```',
    );
    const user = userEvent.setup();
    renderChatSidebar({ activeSection: "entities", scenarioId: SCENARIO_ID });

    await user.click(screen.getByRole("button", { name: /\+ Add Entity/i }));

    await waitFor(() =>
      expect(createdPayload).toMatchObject({ canonical_name: "The Warden" }),
    );
  });

  it("applies a batch of entity + fact blocks, resolving the temp_id to a real entity_id", async () => {
    let factPayload: unknown = null;
    server.use(
      http.post(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`, () =>
        HttpResponse.json(
          {
            entity_id: "99999999-9999-9999-9999-999999999999",
            scenario_id: SCENARIO_ID,
          },
          { status: 201 },
        ),
      ),
      http.post(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}/facts`,
        async ({ request }) => {
          factPayload = await request.json();
          return HttpResponse.json(
            {
              fact_id: "fact-1",
              scenario_id: SCENARIO_ID,
              ...(factPayload as Record<string, unknown>),
            },
            { status: 201 },
          );
        },
      ),
    );
    seedMasterMessage(
      "Villain and crown:\n" +
        '```action:entity {"temp_id":"villain"}\n{"entity_type":"character","canonical_name":"The Warden"}\n```\n' +
        '```action:fact\n{"subject_ref":"villain","predicate":"owns","object_literal":"the crown"}\n```',
    );
    const user = userEvent.setup();
    renderChatSidebar({ activeSection: "entities", scenarioId: SCENARIO_ID });

    await user.click(screen.getByRole("button", { name: /Apply All \(2\)/i }));

    await waitFor(() =>
      expect(factPayload).toMatchObject({
        subject_entity_id: "99999999-9999-9999-9999-999999999999",
        predicate: "owns",
        object_literal: "the crown",
      }),
    );
  });

  it("appends a failed apply as a chat message instead of a toast", async () => {
    server.use(
      http.post(`${API_URL}/v1/scenarios/${SCENARIO_ID}/entities`, () =>
        HttpResponse.json(
          { detail: "Duplicate entity name." },
          { status: 409 },
        ),
      ),
    );
    seedMasterMessage(
      '```action:entity\n{"entity_type":"character","canonical_name":"The Warden"}\n```',
    );
    const user = userEvent.setup();
    renderChatSidebar({ activeSection: "entities", scenarioId: SCENARIO_ID });

    await user.click(screen.getByRole("button", { name: /\+ Add Entity/i }));

    expect(
      await screen.findByText(/Duplicate entity name/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/^Undo$/i)).not.toBeInTheDocument();
  });

  it("routes a delete-op block through the destructive confirm modal before deleting", async () => {
    let deleteCalled = false;
    server.use(
      http.delete(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}/entities/entity-1`,
        () => {
          deleteCalled = true;
          return new HttpResponse(null, { status: 204 });
        },
      ),
    );
    seedMasterMessage(
      'Removing an outdated entity:\n```action:entity {"op":"delete"}\n{"entity_id":"entity-1"}\n```',
    );
    const user = userEvent.setup();
    renderChatSidebar({ activeSection: "entities", scenarioId: SCENARIO_ID });

    await user.click(screen.getByRole("button", { name: /Delete Entity/i }));
    expect(deleteCalled).toBe(false);
    expect(screen.getByText("Confirm Removal")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^Delete$/i }));

    await waitFor(() => expect(deleteCalled).toBe(true));
  });

  it("opens a review modal prefilled with the AI's suggested condition, and creates it on Save", async () => {
    let createdPayload: unknown = null;
    server.use(
      http.post(
        `${API_URL}/v1/scenarios/${SCENARIO_ID}/conditions`,
        async ({ request }) => {
          createdPayload = await request.json();
          return HttpResponse.json(
            { condition_id: "condition-1", scenario_id: SCENARIO_ID },
            { status: 201 },
          );
        },
      ),
    );
    seedMasterMessage(
      "Here is a rule:\n```action:condition\n" +
        '{"label": "Bribe Available", "narrator_instruction": "Offer a bribe.", ' +
        '"condition_expression": {"field": "gold", "op": ">=", "value": 100}}\n```',
    );
    const user = userEvent.setup();
    renderChatSidebar({ activeSection: "conditions", scenarioId: SCENARIO_ID });

    await user.click(
      screen.getByRole("button", { name: /Review Active Rule/i }),
    );

    expect(
      screen.getByText("Review Suggested Active Rule"),
    ).toBeInTheDocument();
    expect(screen.getByDisplayValue("Bribe Available")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^Save$/i }));

    await waitFor(() =>
      expect(createdPayload).toMatchObject({
        label: "Bribe Available",
        condition_expression: { field: "gold", op: ">=", value: 100 },
      }),
    );
  });

  it("shows a validation warning on a condition block the backend flagged as referencing an unknown field", async () => {
    const user = userEvent.setup();
    renderChatSidebar({ activeSection: "conditions", scenarioId: SCENARIO_ID });

    await user.type(
      screen.getByPlaceholderText(/ask anything/i),
      "Add a bribe condition{Enter}",
    );

    expect(capturedSSEHandlers).not.toBeNull();
    const chunk =
      'Here is a rule:\n```action:condition\n{"label": "Bribe", ' +
      '"narrator_instruction": "Offer.", "condition_expression": ' +
      '{"field": "mana", "op": ">=", "value": 10}}\n```';
    capturedSSEHandlers?.onEvent("chunk", chunk);
    capturedSSEHandlers?.onEvent(
      "done",
      JSON.stringify({
        block_validation: [
          {
            index: 0,
            errors: [
              "Unknown field 'mana' — not found in tracked values or entity attributes.",
            ],
          },
        ],
      }),
    );

    expect(
      await screen.findByText(/Unknown field 'mana'/i),
    ).toBeInTheDocument();
  });
});
