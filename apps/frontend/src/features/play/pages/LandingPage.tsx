import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { HeroSection } from "../components/HeroSection";
import { ScenarioCarousel } from "../components/ScenarioCarousel";
import {
  trendingScenarios,
  epicAdventures,
  newArrivals,
} from "../mock/scenarios";
import { Link } from "react-router-dom";
import { UserIcon } from "../../../shared/components/icons/PixelIcons";

export const LandingPage: React.FC = () => {
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.6 }}
        className="min-h-screen bg-[#0d0f14] flex flex-col"
      >
        {/* Top Navbar */}
        <header
          className={`fixed top-0 w-full z-50 transition-all duration-300 ${
            isScrolled
              ? "bg-[#0d0f14]/90 backdrop-blur-md shadow-lg shadow-black/50 py-4"
              : "bg-transparent py-8"
          }`}
        >
          <div className="container mx-auto px-12 md:px-24 flex justify-between items-center">
            <div className="font-fell-sc text-3xl text-white tracking-widest font-bold">
              AI-DND
            </div>
            <nav className="hidden md:flex gap-10 font-mono text-sm tracking-wider text-zinc-400 uppercase">
              <a href="#" className="hover:text-white transition-colors">
                Home
              </a>
              <a href="#" className="hover:text-white transition-colors">
                Inventory
              </a>
              <a href="#" className="hover:text-white transition-colors">
                About
              </a>
            </nav>
            <div className="flex items-center gap-4">
              <Link
                to="/login"
                className="flex items-center gap-2 text-zinc-300 font-mono text-sm hover:text-emerald-400 transition-colors"
              >
                <UserIcon className="w-5 h-5" /> LOGIN
              </Link>
            </div>
          </div>
        </header>

        {/* Hero Section */}
        <HeroSection onPlayClick={() => console.log("Play Featured clicked")} />

        {/* Carousels Section - Give more whitespace and negative margin */}
        <main className="relative z-10 -mt-24 pb-32 space-y-0">
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
