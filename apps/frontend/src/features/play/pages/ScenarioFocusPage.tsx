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
      <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center text-zinc-400 font-mono gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
        <span>Consulting the Ancient Archives...</span>
      </div>
    );
  }

  if (isError || !scenario) {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center p-6 text-center space-y-4">
        <div className="text-4xl">📜</div>
        <h1 className="font-fell-sc text-3xl font-bold text-white">
          Scenario Not Found
        </h1>
        <p className="font-mono text-sm text-zinc-400 max-w-md">
          The requested chronicle could not be located in the realm archives or
          has been archived by its author.
        </p>
        <button
          onClick={() => navigate("/discover")}
          className="rounded-xl bg-zinc-900 border border-zinc-800 px-6 py-3 font-mono text-sm text-amber-300 hover:bg-zinc-800 transition-colors"
        >
          ← Return to Discovery Feed
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 selection:bg-amber-500/30 selection:text-amber-200 pb-20">
      {/* Top Header Navigation */}
      <header className="sticky top-0 z-50 border-b border-zinc-800/80 bg-zinc-950/90 backdrop-blur-md px-4 py-3 md:px-8">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/80 px-3.5 py-1.5 font-mono text-xs text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors"
          >
            ← Back
          </button>
          <span className="font-fell-sc text-sm font-bold text-amber-200/90 truncate max-w-xs md:max-w-md">
            {scenario.title}
          </span>
          <button
            onClick={() => navigate("/discover")}
            className="font-mono text-xs text-zinc-400 hover:text-amber-300 transition-colors"
          >
            Explore Feed
          </button>
        </div>
      </header>

      {/* Main Focus Container */}
      <main className="max-w-7xl mx-auto px-4 md:px-8 pt-6 space-y-8">
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
