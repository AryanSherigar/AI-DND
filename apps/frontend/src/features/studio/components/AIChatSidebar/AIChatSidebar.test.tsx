import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { useStudioStore } from "../../stores/studio.store";
import { AIChatSidebar } from "./AIChatSidebar";

describe("AIChatSidebar", () => {
  beforeEach(() => {
    localStorage.clear();
    useStudioStore.getState().resetDraft();
  });

  it("renders header, default welcome message, and dynamic prompt chips", () => {
    render(<AIChatSidebar activeSection="meta" />);

    expect(screen.getByText("AI Co-Author")).toBeInTheDocument();
    expect(screen.getByText(/Greetings, creator/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: /\+ Suggest 3 catchy scenario titles/i,
      }),
    ).toBeInTheDocument();
  });

  it("switches prompt chips when activeSection changes", () => {
    const { rerender } = render(<AIChatSidebar activeSection="meta" />);
    expect(
      screen.getByRole("button", {
        name: /\+ Suggest 3 catchy scenario titles/i,
      }),
    ).toBeInTheDocument();

    rerender(<AIChatSidebar activeSection="lore" />);
    expect(
      screen.getByRole("button", { name: /\+ Brainstorm 3 unique factions/i }),
    ).toBeInTheDocument();
  });

  it("clears chat history when Clear button is clicked", async () => {
    const user = userEvent.setup();
    const initialMessages = [
      {
        id: "msg-1",
        role: "user",
        content: "Custom history message",
        timestamp: Date.now(),
      },
    ];
    localStorage.setItem(
      "aidnd_studio_assistant_chat",
      JSON.stringify(initialMessages),
    );

    render(<AIChatSidebar activeSection="meta" />);
    expect(screen.getByText("Custom history message")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /clear/i }));

    expect(
      screen.queryByText("Custom history message"),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/Greetings, creator/i)).toBeInTheDocument();
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
      "aidnd_studio_assistant_chat",
      JSON.stringify(messagesWithAction),
    );

    render(<AIChatSidebar activeSection="lore" />);

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
      "aidnd_studio_assistant_chat",
      JSON.stringify(messagesWithAction),
    );

    render(<AIChatSidebar activeSection="lore" />);

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
      "aidnd_studio_assistant_chat",
      JSON.stringify(messagesWithTitleAction),
    );

    const { Step1Meta } = await import("../NewbieWizard/Step1Meta");
    const { QueryClient, QueryClientProvider } = await import(
      "@tanstack/react-query"
    );
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
