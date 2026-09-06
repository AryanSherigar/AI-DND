import React from "react";
import { Footer } from "@/shared/components/layout/Footer";
import { FeaturedHero } from "../components/FeaturedHero";
import { ScenarioCarousel } from "@/features/play/components/DiscoveryFeed/ScenarioCarousel";
import {
  trendingScenarios,
  epicAdventures,
  newArrivals,
} from "@/features/play/mock/scenarios";

export const LandingPage: React.FC = () => {
  return (
    <div className="custom-scrollbar flex-1 overflow-y-auto">
      <FeaturedHero scenarios={trendingScenarios} />

      <div className="space-y-14 py-14">
        <ScenarioCarousel title="Trending now" scenarios={trendingScenarios} />
        <ScenarioCarousel title="Epic adventures" scenarios={epicAdventures} />
        <ScenarioCarousel title="New arrivals" scenarios={newArrivals} />
      </div>

      <Footer />
    </div>
  );
};
