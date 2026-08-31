import React from "react";
import { motion } from "framer-motion";
import { PlayIcon } from "../../../shared/components/icons/PixelIcons";
import { LivingBookHero } from "../../landing/components/LivingBookHero";

interface HeroSectionProps {
  onPlayClick?: () => void;
}

export const HeroSection: React.FC<HeroSectionProps> = ({ onPlayClick }) => {
  return (
    <LivingBookHero>
      {/* Soft gradients for text readability without obscuring image */}
      <div className="absolute inset-0 bg-gradient-to-b from-zinc-950/60 via-transparent to-transparent pointer-events-none" />
      <div className="absolute inset-0 bg-gradient-to-r from-zinc-950/70 via-zinc-950/30 to-transparent pointer-events-none" />

      {/* Seamless bottom fade into page background (#0d0f14) */}
      <div className="absolute bottom-0 left-0 right-0 h-[28rem] bg-gradient-to-b from-transparent via-[#0d0f14]/80 to-[#0d0f14] pointer-events-none z-10" />

      {/* Content */}
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
        className="absolute inset-0 flex flex-col justify-center px-12 md:px-24 pointer-events-none"
      >
        <h1 className="font-fell-sc text-5xl md:text-7xl font-bold text-white max-w-4xl mb-6 leading-tight tracking-wide drop-shadow-2xl">
          Enter the Narrative Threshold
        </h1>
        <p className="font-fell font-normal text-xl md:text-2xl text-zinc-300 max-w-2xl mb-12 leading-relaxed">
          Step into a world of endless possibilities where your choices shape
          the narrative.
        </p>

        <div className="flex gap-6 pointer-events-auto">
          <button
            onClick={onPlayClick}
            className="bg-white text-zinc-950 font-mono text-lg font-bold px-10 py-4 hover:scale-105 hover:bg-zinc-200 transition-all duration-300 ease-out flex items-center gap-3 shadow-[0_0_20px_rgba(255,255,255,0.3)]"
            style={{
              clipPath:
                "polygon(10px 0, 100% 0, 100% calc(100% - 10px), calc(100% - 10px) 100%, 0 100%, 0 10px)",
            }}
          >
            <span>
              <PlayIcon className="w-6 h-6" />
            </span>{" "}
            ENTER WORLD
          </button>
        </div>
      </motion.div>
    </LivingBookHero>
  );
};
