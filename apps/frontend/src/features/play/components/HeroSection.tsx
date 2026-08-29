import React from 'react';
import { motion } from 'framer-motion';
import { PlayIcon } from '../../../shared/components/icons/PixelIcons';

interface HeroSectionProps {
  onPlayClick?: () => void;
}

export const HeroSection: React.FC<HeroSectionProps> = ({ onPlayClick }) => {
  return (
    <div className="relative w-full h-screen overflow-hidden">
      {/* Background Image */}
      <motion.div
        initial={{ scale: 1.05, opacity: 0 }}
        animate={{ scale: 1, opacity: 0.9 }}
        transition={{ duration: 1.2, ease: 'easeOut' }}
        className="absolute inset-0 bg-cover bg-center"
        style={{ backgroundImage: "url('/hero-portal.png')" }}
      />

      {/* Gradients for readability */}
      <div className="absolute inset-0 bg-gradient-to-b from-zinc-950/60 via-transparent to-zinc-950/90" />
      <div className="absolute inset-0 bg-gradient-to-r from-zinc-950/80 to-transparent" />

      {/* Content */}
      <motion.div 
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
        className="absolute inset-0 flex flex-col justify-center px-12 md:px-24"
      >
        <h1 className="font-pixelify text-5xl md:text-7xl text-white max-w-4xl mb-6 leading-tight tracking-wide drop-shadow-2xl">
          Enter the Narrative Threshold
        </h1>
        <p className="font-manrope font-medium text-xl md:text-2xl text-zinc-300 max-w-2xl mb-12">
          Step into a world of endless possibilities where your choices shape the narrative.
        </p>

        <div className="flex gap-6">
          <button
            onClick={onPlayClick}
            className="bg-white text-zinc-950 font-pixelify text-2xl px-10 py-4 hover:scale-105 hover:bg-zinc-200 transition-all duration-300 ease-out flex items-center gap-3 shadow-[0_0_20px_rgba(255,255,255,0.3)]"
            style={{ clipPath: 'polygon(10px 0, 100% 0, 100% calc(100% - 10px), calc(100% - 10px) 100%, 0 100%, 0 10px)' }}
          >
            <span><PlayIcon className="w-6 h-6" /></span> ENTER WORLD
          </button>
        </div>
      </motion.div>
    </div>
  );
};
