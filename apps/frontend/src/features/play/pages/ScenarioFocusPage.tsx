import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useScenarioFocus } from "../hooks/useScenarioFocus";
import { ScenarioBannerHero } from "../components/ScenarioFocus/ScenarioBannerHero";
import { ScenarioLoreSection } from "../components/ScenarioFocus/ScenarioLoreSection";
import { ScenarioSetupPreview } from "../components/ScenarioFocus/ScenarioSetupPreview";
import { ScenarioReviewsSection } from "../components/ScenarioFocus/ScenarioReviewsSection";
import { ScenarioPublicPlaythroughs } from "../components/ScenarioFocus/ScenarioPublicPlaythroughs";

export const ScenarioFocusPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const {
    scenario,
    isLoading,
    isError,
    reviews,
    totalReviews,
    averageRating,
    publicPlaythroughs,
    isBookmarked,
    toggleBookmark,
    isTogglingBookmark,
    submitReview,
    isSubmittingReview,
    currentUser,
  } = useScenarioFocus(id);

  if (isLoading) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 pt-14 font-mono text-content-faint">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
        <span>Consulting the Ancient Archives...</span>
      </div>
    );
  }

  if (isError || !scenario) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center space-y-4 p-6 pt-14 text-center text-content">
        <div className="text-4xl">📜</div>
        <h1 className="font-display text-3xl font-bold text-white">
          Scenario Not Found
        </h1>
        <p className="font-mono text-sm text-content-muted max-w-md">
          The requested chronicle could not be located in the realm archives or
          has been archived by its author.
        </p>
        <button
          onClick={() => navigate("/discover")}
          className="rounded-xl bg-surface border border-border-subtle px-6 py-3 font-mono text-sm text-accent hover:bg-surface-overlay transition-colors"
        >
          ← Return to Discovery Feed
        </button>
      </div>
    );
  }

  return (
    <div className="custom-scrollbar flex-1 overflow-y-auto pb-20 text-content selection:bg-accent/30">
      {/* Main Focus Container */}
      <main className="mx-auto max-w-7xl space-y-8 px-4 pt-16 md:px-8">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 font-mono text-xs text-content-faint transition-colors hover:text-content"
        >
          ← Back
        </button>

        {/* Banner Hero */}
        <ScenarioBannerHero
          scenario={scenario}
          isBookmarked={isBookmarked}
          onToggleBookmark={toggleBookmark}
          isTogglingBookmark={isTogglingBookmark}
          currentUserId={currentUser?.user_id}
        />

        {/* Continuous Scroll Content Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Column: Lore & Setup */}
          <div className="lg:col-span-2 space-y-8">
            <ScenarioLoreSection scenario={scenario} />
            <ScenarioSetupPreview setupSchema={scenario.setup_schema} />
            <ScenarioReviewsSection
              reviews={reviews}
              totalReviews={totalReviews}
              averageRating={averageRating}
              canReview={Boolean(scenario.can_review)}
              onSubmitReview={submitReview}
              isSubmittingReview={isSubmittingReview}
            />
          </div>

          {/* Sidebar Column: Public Playthroughs & Info */}
          <div className="space-y-8">
            <ScenarioPublicPlaythroughs playthroughs={publicPlaythroughs} />
          </div>
        </div>
      </main>
    </div>
  );
};
