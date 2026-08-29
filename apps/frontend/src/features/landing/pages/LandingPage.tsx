import React, { useState, useEffect, useRef } from 'react';
import { Header } from '@/shared/components/layout/Header';
import { HeroContent } from '../components/HeroContent';
import { ScenarioCarousel } from '../components/ScenarioCarousel';

const FEATURED_SCENARIOS = [
  {
    id: '1',
    title: 'Starlight Tavern',
    description: 'A cozy sanctuary at the edge of the galaxy, where adventurers gather to share tales under an infinite starry sky.',
    imageUrl: 'https://images.unsplash.com/photo-1478131143081-80f7f84ca84d?q=80&w=2940&auto=format&fit=crop',
  },
  {
    id: '2',
    title: 'The Whispering Woods',
    description: 'An ancient forest where the trees hold secrets of a forgotten era. Navigate the shadows and discover what lies beneath the roots.',
    imageUrl: 'https://images.unsplash.com/photo-1542273917363-3b1817f69a5d?q=80&w=2948&auto=format&fit=crop',
  },
  {
    id: '3',
    title: 'Crimson Citadel',
    description: 'A towering fortress carved from red stone, suspended over a river of magma. Will you conquer its fiery depths?',
    imageUrl: 'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?q=80&w=2784&auto=format&fit=crop',
  },
  {
    id: '4',
    title: 'Echoes of the Abyss',
    description: 'A submerged ruined city populated by glowing bioluminescent flora. The deeper you go, the darker the truth becomes.',
    imageUrl: 'https://images.unsplash.com/photo-1682687982501-1e5898cb8f4b?q=80&w=2940&auto=format&fit=crop',
  }
];

export const LandingPage: React.FC = () => {
  const [activeIndex, setActiveIndex] = useState(0);
  const scrollTimeout = useRef<number | null>(null);

  const handleWheel = (e: React.WheelEvent) => {
    // Debounce the wheel event slightly to prevent rapid firing
    if (scrollTimeout.current) return;

    if (e.deltaY > 0) {
      // Scroll down -> next
      setActiveIndex((prev) => Math.min(prev + 1, FEATURED_SCENARIOS.length - 1));
    } else if (e.deltaY < 0) {
      // Scroll up -> prev
      setActiveIndex((prev) => Math.max(prev - 1, 0));
    }

    scrollTimeout.current = setTimeout(() => {
      scrollTimeout.current = null;
    }, 800); // 800ms cooldown for scrolling to next image
  };

  // Preload images
  useEffect(() => {
    FEATURED_SCENARIOS.forEach(scenario => {
      const img = new Image();
      img.src = scenario.imageUrl;
    });
  }, []);

  return (
    <div 
      className="relative h-screen w-full overflow-hidden bg-black text-white selection:bg-white/30"
      onWheel={handleWheel}
    >
      {/* Background Images with Crossfade */}
      {FEATURED_SCENARIOS.map((scenario, index) => (
        <div
          key={scenario.id}
          className={`absolute inset-0 transition-opacity duration-1000 ease-in-out ${
            index === activeIndex ? 'opacity-100 z-0' : 'opacity-0 -z-10'
          }`}
        >
          <img 
            src={scenario.imageUrl} 
            alt={scenario.title} 
            className="w-full h-full object-cover opacity-60"
          />
          {/* Dark gradient overlay for readability */}
          <div className="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-black/20" />
        </div>
      ))}

      <Header />

      <HeroContent activeScenario={FEATURED_SCENARIOS[activeIndex]} />

      <ScenarioCarousel 
        scenarios={FEATURED_SCENARIOS} 
        activeIndex={activeIndex} 
        onSelectIndex={setActiveIndex} 
      />
    </div>
  );
};
