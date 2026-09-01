import React, { useState, useEffect } from "react";

interface DramaticSetupLoaderProps {
  scenarioTitle?: string;
  onComplete?: () => void;
}

const LOADING_PHRASES = [
  "Weaving the threads of fate...",
  "Binding choices into reality...",
  "Synthesizing initial world state...",
  "Awakening the AI Narrator...",
  "Opening the portal...",
];

export const DramaticSetupLoader: React.FC<DramaticSetupLoaderProps> = ({
  scenarioTitle,
  onComplete,
}) => {
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    // Progress increment interval
    const progressInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(progressInterval);
          return 100;
        }
        return prev + 2;
      });
    }, 45);

    // Text phrase rotation interval
    const phraseInterval = setInterval(() => {
      setPhraseIndex((prev) => (prev + 1) % LOADING_PHRASES.length);
    }, 600);

    return () => {
      clearInterval(progressInterval);
      clearInterval(phraseInterval);
    };
  }, []);

  useEffect(() => {
    if (progress >= 100 && onComplete) {
      const timeout = setTimeout(() => {
        onComplete();
      }, 300);
      return () => clearTimeout(timeout);
    }
    return undefined;
  }, [progress, onComplete]);

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-zinc-950/95 backdrop-blur-xl px-6 text-center select-none overflow-hidden">
      {/* Background Ambient Radial Glow */}
      <div className="absolute w-[500px] h-[500px] bg-amber-500/10 rounded-full blur-[120px] pointer-events-none animate-pulse" />

      {/* Runic Magic Circle Engine */}
      <div className="relative w-44 h-44 mb-8 flex items-center justify-center">
        {/* Outer Rotating Dash Ring */}
        <svg
          className="absolute inset-0 w-full h-full text-amber-500/40 animate-[spin_12s_linear_infinite]"
          viewBox="0 0 100 100"
        >
          <circle
            cx="50"
            cy="50"
            r="46"
            fill="none"
            stroke="currentColor"
            strokeWidth="1"
            strokeDasharray="4 6"
          />
        </svg>

        {/* Counter-rotating Inner Rune Ring */}
        <svg
          className="absolute inset-2 w-[calc(100%-16px)] h-[calc(100%-16px)] text-amber-400/60 animate-[spin_8s_linear_infinite_reverse]"
          viewBox="0 0 100 100"
        >
          <circle
            cx="50"
            cy="50"
            r="44"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeDasharray="12 4"
          />
          <polygon
            points="50,10 85,75 15,75"
            fill="none"
            stroke="currentColor"
            strokeWidth="0.75"
            className="opacity-40"
          />
          <polygon
            points="50,90 15,25 85,25"
            fill="none"
            stroke="currentColor"
            strokeWidth="0.75"
            className="opacity-40"
          />
        </svg>

        {/* Inner Glowing Core Sigil */}
        <div className="w-16 h-16 rounded-full bg-amber-500/10 border border-amber-500/40 flex items-center justify-center shadow-[0_0_30px_rgba(245,158,11,0.3)] animate-pulse">
          <span className="font-serif text-2xl text-amber-300 font-bold tracking-widest">
            ❖
          </span>
        </div>
      </div>

      {/* Title & Phase Text */}
      <div className="space-y-3 max-w-md">
        {scenarioTitle && (
          <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-500 block">
            {scenarioTitle}
          </span>
        )}
        <h2 className="font-serif text-2xl md:text-3xl text-zinc-100 font-bold tracking-wide transition-all duration-300 min-h-[40px] flex items-center justify-center">
          {LOADING_PHRASES[phraseIndex]}
        </h2>
        <p className="font-mono text-xs text-amber-400/80 tracking-widest uppercase">
          INITIATING PLAYTHROUGH • {progress}%
        </p>
      </div>

      {/* Atmospheric Progress Bar */}
      <div className="mt-8 w-64 h-1 bg-zinc-900 rounded-full overflow-hidden border border-zinc-800/80 relative">
        <div
          className="h-full bg-gradient-to-r from-amber-600 via-amber-400 to-amber-300 transition-all duration-75 ease-out rounded-full shadow-[0_0_12px_rgba(245,158,11,0.6)]"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
};
