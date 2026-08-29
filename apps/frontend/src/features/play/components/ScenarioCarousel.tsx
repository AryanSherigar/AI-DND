import React, { useRef } from 'react';
import { motion, Variants } from 'framer-motion';
import { ScenarioMock } from '../types/scenario';
import { ScenarioCard } from './ScenarioCard';

interface ScenarioCarouselProps {
  title: string;
  scenarios: ScenarioMock[];
}

export const ScenarioCarousel: React.FC<ScenarioCarouselProps> = ({ title, scenarios }) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const scroll = (direction: 'left' | 'right') => {
    if (scrollContainerRef.current) {
      const scrollAmount = direction === 'left' ? -800 : 800;
      scrollContainerRef.current.scrollBy({ left: scrollAmount, behavior: 'smooth' });
    }
  };

  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.1 }
    }
  };

  const itemVariants: Variants = {
    hidden: { opacity: 0, x: 50 },
    show: { opacity: 1, x: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } }
  };

  return (
    <motion.div 
      variants={containerVariants}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-100px" }}
      className="w-full py-4 relative group"
    >
      <h2 className="font-pixelify text-3xl md:text-4xl text-white mb-6 px-12 md:px-24 tracking-wide drop-shadow-md">
        {title}
      </h2>
      
      {/* Scroll Controls - Appear on hover */}
      <button 
        onClick={() => scroll('left')}
        className="absolute left-0 top-1/2 -translate-y-1/2 z-20 h-full w-12 md:w-24 bg-gradient-to-r from-zinc-950 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-center text-white text-4xl font-vt323 hover:text-emerald-400"
      >
        {'<'}
      </button>
      
      <button 
        onClick={() => scroll('right')}
        className="absolute right-0 top-1/2 -translate-y-1/2 z-20 h-full w-12 md:w-24 bg-gradient-to-l from-zinc-950 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-center text-white text-4xl font-vt323 hover:text-emerald-400"
      >
        {'>'}
      </button>

      {/* Carousel Container */}
      <div 
        ref={scrollContainerRef}
        className="flex overflow-x-auto gap-8 pb-12 pt-4 snap-x snap-mandatory hide-scrollbar scroll-pl-12 md:scroll-pl-24"
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        {scenarios.map((scenario, index) => (
          <motion.div 
            variants={itemVariants} 
            key={scenario.id} 
            className={`snap-start shrink-0 ${index === 0 ? 'ml-12 md:ml-24' : ''} ${index === scenarios.length - 1 ? 'mr-12 md:mr-24' : ''}`}
          >
            <ScenarioCard scenario={scenario} />
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
};
