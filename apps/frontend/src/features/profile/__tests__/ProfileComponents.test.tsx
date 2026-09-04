import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ProfileStatsRibbon } from "../components/ProfileStatsRibbon";
import { ProfileHeader } from "../components/ProfileHeader";
import { CampaignCard } from "../components/cards/CampaignCard";
import { UserReviewCard } from "../components/cards/UserReviewCard";
import {
  UserProfile,
  UserPlaythroughSummary,
  UserReviewSummary,
} from "../types/profile.types";

const mockProfile: UserProfile = {
  user_id: "user-123",
  display_name: "Elminster",
  bio: "Archmage of Shadowdale",
  avatar_url: "/avatars/mage.webp",
  banner_url: "/banners/portal.png",
  created_at: "2026-01-15T00:00:00Z",
  stats: {
    campaigns_played_count: 7,
    victories_count: 5,
    total_turns_taken: 84,
    scenarios_authored_count: 3,
    total_plays_received: 120,
  },
};

describe("ProfileComponents", () => {
  it("renders ProfileStatsRibbon with all 5 stats", () => {
    render(<ProfileStatsRibbon stats={mockProfile.stats} />);
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("84")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument();
    expect(screen.getByText("Campaigns")).toBeInTheDocument();
    expect(screen.getByText("Victories")).toBeInTheDocument();
    expect(screen.getByText("Turns Taken")).toBeInTheDocument();
  });

  it("renders ProfileHeader with adventurer details and edit button for owner", () => {
    const handleEdit = vi.fn();
    render(
      <ProfileHeader
        profile={mockProfile}
        isOwner={true}
        onEditClick={handleEdit}
      />,
    );

    expect(screen.getByText("Elminster")).toBeInTheDocument();
    expect(screen.getByText("Archmage of Shadowdale")).toBeInTheDocument();
    expect(screen.getByText(/Adventurer since/)).toBeInTheDocument();

    const editBtn = screen.getByText("✦ Edit Chronicle");
    expect(editBtn).toBeInTheDocument();
    fireEvent.click(editBtn);
    expect(handleEdit).toHaveBeenCalledTimes(1);
  });

  it("hides edit button when isOwner is false", () => {
    render(
      <ProfileHeader
        profile={mockProfile}
        isOwner={false}
        onEditClick={vi.fn()}
      />,
    );
    expect(screen.queryByText("✦ Edit Chronicle")).not.toBeInTheDocument();
  });

  it("renders CampaignCard with active status and handles abandon confirmation", () => {
    const mockCampaign: UserPlaythroughSummary = {
      playthrough_id: "pt-1",
      scenario_id: "sc-1",
      scenario_title: "Curse of Strahd",
      scenario_mode: "master",
      cover_image_url: null,
      turn_count: 22,
      status: "active",
      ended_outcome_tag: null,
      ended_outcome_title: null,
      ended_outcome_text: null,
      character_name: "Drizzt",
      character_archetype: "Ranger",
      created_at: "2026-02-01T00:00:00Z",
      updated_at: "2026-02-01T00:00:00Z",
    };

    const handleAbandon = vi.fn();

    render(
      <MemoryRouter>
        <CampaignCard campaign={mockCampaign} onAbandon={handleAbandon} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Curse of Strahd")).toBeInTheDocument();
    expect(screen.getByText("Active Run")).toBeInTheDocument();
    expect(screen.getByText("Resume Run")).toBeInTheDocument();
    expect(screen.getByText(/Turn 22/)).toBeInTheDocument();

    // Click abandon
    const abandonBtn = screen.getByText("Abandon");
    fireEvent.click(abandonBtn);

    // Confirm prompt shows up
    expect(screen.getByText("Abandon run?")).toBeInTheDocument();
    const yesBtn = screen.getByText("Yes");
    fireEvent.click(yesBtn);
    expect(handleAbandon).toHaveBeenCalledWith("pt-1");
  });

  it("renders UserReviewCard with scenario title, comment, and star rating", () => {
    const mockReview: UserReviewSummary = {
      review_id: "rev-1",
      scenario_id: "sc-2",
      scenario_title: "Tomb of Horrors",
      rating: 4,
      review_text: "A treacherous dungeon with ingenious traps!",
      created_at: "2026-03-01T00:00:00Z",
    };

    render(
      <MemoryRouter>
        <UserReviewCard review={mockReview} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Tomb of Horrors")).toBeInTheDocument();
    expect(
      screen.getByText(/A treacherous dungeon with ingenious traps!/),
    ).toBeInTheDocument();
    expect(screen.getByText("★★★★☆")).toBeInTheDocument();
  });
});
