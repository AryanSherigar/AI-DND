import React from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Header } from "@/shared/components/layout/Header";
import { HeroSection } from "../components/HeroSection";
import { ScenarioCarousel } from "@/features/play/components/DiscoveryFeed/ScenarioCarousel";
import {
  trendingScenarios,
  epicAdventures,
  newArrivals,
} from "@/features/play/mock/scenarios";

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();

  const handlePlayFeatured = () => {
    navigate("/discover");
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.6 }}
        className="min-h-screen bg-[#0d0f14] flex flex-col"
      >
        <Header variant="landing" />

        {/* Hero Section */}
        <HeroSection onPlayClick={handlePlayFeatured} />

        {/* Carousels Section */}
        <main className="relative z-20 -mt-28 pb-32 space-y-0">
          <ScenarioCarousel
            title="Trending Now"
            scenarios={trendingScenarios}
          />
          <ScenarioCarousel
            title="Epic Adventures"
            scenarios={epicAdventures}
          />
          <ScenarioCarousel title="New Arrivals" scenarios={newArrivals} />
        </main>
      </motion.div>
    </AnimatePresence>
  );
};
