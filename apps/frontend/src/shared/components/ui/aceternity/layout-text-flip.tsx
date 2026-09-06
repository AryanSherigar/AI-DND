import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { cn } from "@/shared/lib/cn";

type FlipSize = "sm" | "md" | "lg";

const SIZE_CLASSES: Record<FlipSize, string> = {
  sm: "text-lg md:text-xl",
  md: "text-xl md:text-2xl",
  lg: "text-2xl md:text-4xl",
};

export const LayoutTextFlip = ({
  text = "Build Amazing",
  words = ["Landing Pages", "Component Blocks", "Page Sections", "3D Shaders"],
  duration = 3000,
  size = "lg",
  className,
  textClassName,
}: {
  text: string;
  words: string[];
  duration?: number;
  size?: FlipSize;
  className?: string;
  textClassName?: string;
}) => {
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentIndex((prevIndex) => (prevIndex + 1) % words.length);
    }, duration);

    return () => clearInterval(interval);
  }, []);

  return (
    <>
      <motion.span
        layoutId="subtext"
        className={cn(
          "font-bold tracking-tight drop-shadow-lg",
          SIZE_CLASSES[size],
          textClassName,
        )}
      >
        {text}
      </motion.span>

      <motion.span
        layout
        className={cn(
          "relative w-fit overflow-hidden rounded-md border border-transparent bg-white px-3 py-1.5 font-sans font-bold tracking-tight text-black shadow-sm ring shadow-black/10 ring-black/10 drop-shadow-lg dark:bg-neutral-900 dark:text-white dark:shadow-sm dark:ring-1 dark:shadow-white/10 dark:ring-white/10",
          SIZE_CLASSES[size],
          className,
        )}
      >
        <AnimatePresence mode="popLayout">
          <motion.span
            key={currentIndex}
            initial={{ y: -40, filter: "blur(10px)" }}
            animate={{
              y: 0,
              filter: "blur(0px)",
            }}
            exit={{ y: 50, filter: "blur(10px)", opacity: 0 }}
            transition={{
              duration: 0.5,
            }}
            className={cn("inline-block whitespace-nowrap")}
          >
            {words[currentIndex]}
          </motion.span>
        </AnimatePresence>
      </motion.span>
    </>
  );
};
