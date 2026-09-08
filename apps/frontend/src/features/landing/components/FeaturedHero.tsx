import React, { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import {
  IconPlayerPlayFilled,
  IconPlus,
  IconStarFilled,
} from "@tabler/icons-react";
import { cn } from "@/shared/lib/cn";
import { FeaturedHeroProps } from "./FeaturedHero.types";

export const FeaturedHero: React.FC<FeaturedHeroProps> = ({ scenarios }) => {
  const navigate = useNavigate();
  const featured = useMemo(() => scenarios.slice(0, 6), [scenarios]);
  const [activeId, setActiveId] = useState<string>(featured[0]?.id ?? "");

  const active = featured.find((item) => item.id === activeId) ?? featured[0];
  if (!active) return null;

  const handlePlay = (): void => {
    void navigate(`/setup/${active.id}`);
  };

  return (
    <section className="relative isolate min-h-[85vh] w-full overflow-hidden">
      <AnimatePresence mode="popLayout">
        <motion.img
          key={active.id}
          src={active.coverImageUrl}
          alt=""
          aria-hidden="true"
          initial={{ opacity: 0, scale: 1.04 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="absolute inset-0 -z-10 h-full w-full object-cover object-center"
        />
      </AnimatePresence>
      <div className="absolute inset-0 -z-10 bg-gradient-to-r from-surface-raised via-surface-raised/80 to-transparent" />
      <div className="absolute inset-0 -z-10 bg-gradient-to-t from-surface-raised via-surface-raised/10 to-transparent" />

      <div className="flex min-h-[85vh] flex-col justify-end gap-8 px-8 pb-12 pt-24 md:px-14">
        <motion.div
          key={active.id}
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="max-w-xl"
        >
          <h1 className="font-display text-5xl font-bold leading-[1.05] text-content md:text-6xl">
            {active.title}
          </h1>

          <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-sm text-content-muted">
            <span className="flex items-center gap-1 text-accent">
              <IconStarFilled size={14} />
              {active.rating.toFixed(1)}
            </span>
            <span className="text-content-faint">•</span>
            <span>{active.genre}</span>
            <span className="text-content-faint">•</span>
            <span>{active.playerCount.toLocaleString()} plays</span>
            <span className="text-content-faint">•</span>
            <span>by {active.author}</span>
          </div>

          <p className="mt-5 max-w-lg font-sans text-base leading-relaxed text-content-muted">
            {active.logline}
          </p>

          <div className="mt-8 flex items-center gap-3">
            <button
              type="button"
              onClick={handlePlay}
              className="inline-flex items-center gap-2.5 rounded-full bg-content px-7 py-3.5 font-sans text-base font-semibold text-surface transition hover:bg-white active:translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface-raised"
            >
              <IconPlayerPlayFilled size={18} />
              Play now
            </button>
            <Link
              to="/studio/new"
              className="inline-flex items-center gap-2 rounded-full border border-border-strong bg-surface/50 px-6 py-3.5 font-sans text-base font-medium text-content-muted backdrop-blur-sm transition hover:border-content hover:text-content focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface-raised"
            >
              <IconPlus size={18} />
              Create your own
            </Link>
          </div>
        </motion.div>

        {/* Thumbnail strip */}
        <div className="flex max-w-full items-center gap-2 overflow-x-auto pb-1 hide-scrollbar">
          {featured.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setActiveId(item.id)}
              aria-label={item.title}
              className={cn(
                "relative h-16 w-28 shrink-0 overflow-hidden rounded-lg border transition",
                item.id === active.id
                  ? "border-content"
                  : "border-transparent opacity-60 hover:opacity-100",
              )}
            >
              <img
                src={item.coverImageUrl}
                alt=""
                className="h-full w-full object-cover"
              />
            </button>
          ))}
        </div>
      </div>
    </section>
  );
};
