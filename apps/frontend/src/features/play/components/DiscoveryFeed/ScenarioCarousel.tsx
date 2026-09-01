import React, { useRef, useState, useEffect } from "react";
import { motion, Variants } from "framer-motion";
import { ScenarioMock } from "../../types/scenario";
import { ScenarioCard } from "./ScenarioCard";

interface ScenarioCarouselProps {
  title: string;
  scenarios: ScenarioMock[];
}

const CONTAINER_VARIANTS: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1 },
  },
};

const ITEM_VARIANTS: Variants = {
  hidden: { opacity: 0, x: 50 },
  show: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] },
  },
};

const SCROLL_STEP_PX = 900;

export const ScenarioCarousel: React.FC<ScenarioCarouselProps> = ({
  title,
  scenarios,
}) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  const checkScrollBounds = () => {
    if (!scrollContainerRef.current) return;
    const { scrollLeft, scrollWidth, clientWidth } = scrollContainerRef.current;
    setCanScrollLeft(scrollLeft > 10);
    setCanScrollRight(scrollLeft + clientWidth < scrollWidth - 10);
  };

  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    checkScrollBounds();
    el.addEventListener("scroll", checkScrollBounds, { passive: true });
    window.addEventListener("resize", checkScrollBounds);
    return () => {
      el.removeEventListener("scroll", checkScrollBounds);
      window.removeEventListener("resize", checkScrollBounds);
    };
  }, [scenarios]);

  const handleScroll = (direction: "left" | "right") => {
    if (!scrollContainerRef.current) return;
    const scrollAmount =
      direction === "left" ? -SCROLL_STEP_PX : SCROLL_STEP_PX;
    scrollContainerRef.current.scrollBy({
      left: scrollAmount,
      behavior: "smooth",
    });
  };

  return (
    <motion.div
      variants={CONTAINER_VARIANTS}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-100px" }}
      className="group relative w-full py-2"
    >
      <h2 className="mb-3 px-8 sm:px-12 md:px-16 lg:px-24 font-fell-sc text-3xl font-bold tracking-wide text-white drop-shadow-md md:text-4xl">
        {title}
      </h2>

      {canScrollLeft && (
        <button
          onClick={() => handleScroll("left")}
          className="absolute left-0 top-1/2 z-30 flex h-3/4 w-12 -translate-y-1/2 items-center justify-center bg-gradient-to-r from-zinc-950 via-zinc-950/70 to-transparent font-mono text-3xl text-white opacity-0 transition-opacity duration-300 group-hover:opacity-100 hover:text-emerald-400 md:w-16"
          aria-label="Scroll left"
        >
          {"<"}
        </button>
      )}

      {canScrollRight && (
        <button
          onClick={() => handleScroll("right")}
          className="absolute right-0 top-1/2 z-30 flex h-3/4 w-12 -translate-y-1/2 items-center justify-center bg-gradient-to-l from-zinc-950 via-zinc-950/70 to-transparent font-mono text-3xl text-white opacity-0 transition-opacity duration-300 group-hover:opacity-100 hover:text-emerald-400 md:w-16"
          aria-label="Scroll right"
        >
          {">"}
        </button>
      )}

      <div
        ref={scrollContainerRef}
        className="flex overflow-x-auto gap-2.5 pb-4 pt-1 snap-x snap-mandatory hide-scrollbar px-8 sm:px-12 md:px-16 lg:px-24 scroll-px-8 sm:scroll-px-12 md:scroll-px-16 lg:scroll-px-24"
        style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
      >
        {scenarios.map((scenario) => (
          <motion.div
            variants={ITEM_VARIANTS}
            key={scenario.id}
            className="shrink-0 snap-start w-[85vw] sm:w-[320px] lg:w-[calc((100%-1.25rem)/3)]"
          >
            <ScenarioCard scenario={scenario} />
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
};
