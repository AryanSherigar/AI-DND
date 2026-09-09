import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MoodSlotCard } from "./MoodSlotCard";

const SCENARIO_ID = "scenario-1";

const renderCard = (props: React.ComponentProps<typeof MoodSlotCard>): void => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MoodSlotCard {...props} />
    </QueryClientProvider>,
  );
};

describe("MoodSlotCard", () => {
  it("renders default track audio preview player using the backend-resolved track_url", () => {
    renderCard({
      scenarioId: SCENARIO_ID,
      mood: "peaceful",
      label: "Peaceful",
      slot: {
        scenario_music_id: "slot-1",
        scenario_id: SCENARIO_ID,
        mood: "peaceful",
        source: "default",
        track_url:
          "https://storage.googleapis.com/test-bucket/default-music/peaceful.wav",
        generation_prompt: null,
        key: null,
        bpm: null,
        duration_seconds: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      quotaExceeded: false,
    });

    const audioElement = screen.getByLabelText(/track preview/i);
    expect(audioElement).toBeInTheDocument();
    expect(audioElement).toHaveAttribute(
      "src",
      "https://storage.googleapis.com/test-bucket/default-music/peaceful.wav",
    );
  });

  it("renders no audio preview player when a default slot has no track_url yet", () => {
    renderCard({
      scenarioId: SCENARIO_ID,
      mood: "peaceful",
      label: "Peaceful",
      slot: {
        scenario_music_id: "slot-1",
        scenario_id: SCENARIO_ID,
        mood: "peaceful",
        source: "default",
        track_url: null,
        generation_prompt: null,
        key: null,
        bpm: null,
        duration_seconds: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      quotaExceeded: false,
    });

    expect(screen.queryByLabelText(/track preview/i)).not.toBeInTheDocument();
  });

  it("renders custom track audio player when track_url is provided", () => {
    renderCard({
      scenarioId: SCENARIO_ID,
      mood: "combat",
      label: "Combat",
      slot: {
        scenario_music_id: "slot-2",
        scenario_id: SCENARIO_ID,
        mood: "combat",
        source: "upload",
        track_url: "https://storage.googleapis.com/test-bucket/combat.mp3",
        generation_prompt: null,
        key: null,
        bpm: null,
        duration_seconds: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      quotaExceeded: false,
    });

    const audioElement = screen.getByLabelText(/track preview/i);
    expect(audioElement).toBeInTheDocument();
    expect(audioElement).toHaveAttribute(
      "src",
      "https://storage.googleapis.com/test-bucket/combat.mp3",
    );
  });
});
