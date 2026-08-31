import React from "react";

interface Scenario {
  id: string;
  title: string;
  imageUrl: string;
}

interface ScenarioCarouselProps {
  scenarios: Scenario[];
  activeIndex: number;
  onSelectIndex: (index: number) => void;
}

export const ScenarioCarousel: React.FC<ScenarioCarouselProps> = ({
  scenarios,
  activeIndex,
  onSelectIndex,
}) => {
  return (
    <div className="absolute bottom-8 left-0 right-0 z-20 flex justify-center px-6">
      <div className="flex items-center gap-4 p-4 bg-white/5 backdrop-blur-xl border border-white/20 rounded-2xl shadow-[inset_0_1px_1px_rgba(255,255,255,0.2),0_8px_32px_rgba(0,0,0,0.5)]">
        {/* Left Arrow */}
        <button
          onClick={() => onSelectIndex(Math.max(activeIndex - 1, 0))}
          disabled={activeIndex === 0}
          className="p-2 text-white/50 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors font-mono text-sm"
        >
          {"<"}
        </button>

        {/* Thumbnails */}
        <div className="flex gap-4 overflow-hidden px-2 max-w-full">
          {scenarios.map((scenario, index) => {
            const isActive = index === activeIndex;
            return (
              <button
                key={scenario.id}
                onClick={() => onSelectIndex(index)}
                className={`relative overflow-hidden rounded-lg transition-all duration-300 ease-out flex-shrink-0
                  ${isActive ? "w-48 h-28 ring-2 ring-emerald-400 shadow-[0_0_15px_rgba(52,211,153,0.5)]" : "w-32 h-20 opacity-60 hover:opacity-100"}
                `}
              >
                <img
                  src={scenario.imageUrl}
                  alt={scenario.title}
                  className="w-full h-full object-cover"
                />
                <div
                  className={`absolute inset-0 bg-gradient-to-t from-black/80 to-transparent flex items-end p-2 transition-opacity ${isActive ? "opacity-100" : "opacity-0"}`}
                >
                  <span className="font-fell-sc font-semibold text-sm text-white text-left leading-tight">
                    {scenario.title}
                  </span>
                </div>
              </button>
            );
          })}
        </div>

        {/* Right Arrow */}
        <button
          onClick={() =>
            onSelectIndex(Math.min(activeIndex + 1, scenarios.length - 1))
          }
          disabled={activeIndex === scenarios.length - 1}
          className="p-2 text-white/50 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors font-mono text-sm"
        >
          {">"}
        </button>
      </div>
    </div>
  );
};
