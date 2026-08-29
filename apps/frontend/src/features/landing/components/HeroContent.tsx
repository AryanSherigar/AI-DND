import React from 'react';
import { Link } from 'react-router-dom';

interface Scenario {
  id: string;
  title: string;
  description: string;
}

interface HeroContentProps {
  activeScenario: Scenario;
}

export const HeroContent: React.FC<HeroContentProps> = ({ activeScenario }) => {
  return (
    <div className="relative z-10 flex flex-col items-center justify-center h-full px-6 pt-16 pb-32 text-center pointer-events-none">
      <h1 className="font-retro text-4xl md:text-5xl lg:text-7xl text-white mb-6 drop-shadow-[0_0_15px_rgba(255,255,255,0.3)] transition-all duration-500">
        Immerse Yourself
      </h1>
      
      <div className="max-w-2xl mx-auto space-y-4">
        <h2 
          key={`title-${activeScenario.id}`} 
          className="font-playfair text-3xl md:text-4xl font-semibold text-emerald-400 drop-shadow-lg transition-all duration-500"
        >
          {activeScenario.title}
        </h2>
        <p 
          key={`desc-${activeScenario.id}`} 
          className="font-playfair text-lg md:text-xl text-zinc-300 leading-relaxed transition-all duration-500 delay-100"
        >
          {activeScenario.description}
        </p>
      </div>

      <div className="mt-10 flex items-center justify-center gap-6 pointer-events-auto">
        <Link 
          to="/login"
          className="px-8 py-4 bg-white/10 hover:bg-white/20 backdrop-blur-md border border-white/30 rounded-lg font-playfair font-semibold text-lg text-white shadow-[inset_0_1px_1px_rgba(255,255,255,0.5),0_4px_20px_rgba(0,0,0,0.5)] transition-all hover:scale-105"
        >
          Play Now
        </Link>
        <Link 
          to="/discover"
          className="px-8 py-4 bg-transparent hover:bg-white/5 border border-transparent hover:border-white/20 rounded-lg font-playfair font-medium text-lg text-white/80 transition-all"
        >
          Learn More
        </Link>
      </div>
    </div>
  );
};
