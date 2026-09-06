import React from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { IconArrowLeft } from "@tabler/icons-react";
import { useScenarioFocus } from "../hooks/useScenarioFocus";
import { Loader } from "@/shared/components/feedback/Loader";
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
      <div className="flex flex-1 items-center justify-center pt-14">
        <Loader size="lg" label="Loading scenario" />
      </div>
    );
  }

  if (isError || !scenario) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 pt-14 text-center">
        <h1 className="font-display text-2xl text-content">Scenario not found</h1>
        <p className="max-w-sm font-sans text-sm text-content-faint">
          It may have been unpublished, or the link is wrong.
        </p>
        <Link
          to="/discover"
          className="mt-2 rounded-full border border-border-subtle bg-surface px-4 py-2 font-sans text-sm text-content-muted transition hover:text-content"
        >
          Back to discover
        </Link>
      </div>
    );
  }

  return (
    <div className="custom-scrollbar flex-1 overflow-y-auto pb-24 text-content selection:bg-accent/30">
      <div className="mx-auto max-w-6xl px-4 pt-16 md:px-10">
        <button
          onClick={() => navigate(-1)}
          className="mb-4 flex items-center gap-1.5 font-mono text-xs text-content-faint transition-colors hover:text-content"
        >
          <IconArrowLeft size={14} />
          Back
        </button>

        <ScenarioBannerHero
          scenario={scenario}
          isBookmarked={isBookmarked}
          onToggleBookmark={toggleBookmark}
          isTogglingBookmark={isTogglingBookmark}
          currentUserId={currentUser?.user_id}
        />

        <div className="mt-12 grid grid-cols-1 gap-x-12 gap-y-12 lg:grid-cols-[1fr_20rem]">
          <div className="space-y-12">
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

          <aside className="lg:border-l lg:border-border-subtle lg:pl-8">
            <ScenarioPublicPlaythroughs playthroughs={publicPlaythroughs} />
          </aside>
        </div>
      </div>
    </div>
  );
};
