import React from "react";
import { Link } from "react-router-dom";
import { Footer } from "@/shared/components/layout/Footer";
import { FeaturedHero } from "../components/FeaturedHero";
import { ScenarioCarousel } from "@/features/play/components/DiscoveryFeed/ScenarioCarousel";
import { useLandingScenarios } from "../hooks/useLandingScenarios";

const EmptyLandingState: React.FC = () => (
  <section className="flex min-h-[70vh] flex-col items-center justify-center gap-4 px-8 text-center">
    <h1 className="font-display text-4xl font-bold text-content">
      No published scenarios yet
    </h1>
    <p className="max-w-md font-sans text-base text-content-muted">
      Be the first to publish a scenario and it will show up here for everyone
      to discover.
    </p>
    <Link
      to="/studio/new"
      className="mt-2 inline-flex items-center gap-2 rounded-full bg-content px-7 py-3.5 font-sans text-base font-semibold text-surface transition hover:bg-white"
    >
      Create your own
    </Link>
  </section>
);

export const LandingPage: React.FC = () => {
  const { trendingScenarios, epicAdventures, newArrivals, isLoading } =
    useLandingScenarios();

  if (isLoading) {
    return <div className="custom-scrollbar flex-1 overflow-y-auto" />;
  }

  if (trendingScenarios.length === 0) {
    return (
      <div className="custom-scrollbar flex-1 overflow-y-auto">
        <EmptyLandingState />
        <Footer />
      </div>
    );
  }

  return (
    <div className="custom-scrollbar flex-1 overflow-y-auto">
      <FeaturedHero scenarios={trendingScenarios} />

      <div className="space-y-14 py-14">
        <ScenarioCarousel title="Trending now" scenarios={trendingScenarios} />
        {epicAdventures.length > 0 && (
          <ScenarioCarousel
            title="Popular adventures"
            scenarios={epicAdventures}
          />
        )}
        {newArrivals.length > 0 && (
          <ScenarioCarousel title="New arrivals" scenarios={newArrivals} />
        )}
      </div>

      <Footer />
    </div>
  );
};
