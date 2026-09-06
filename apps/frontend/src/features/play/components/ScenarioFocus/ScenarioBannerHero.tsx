import React, { useState } from "react";
import { Link } from "react-router-dom";
import {
  IconStarFilled,
  IconUsers,
  IconClock,
  IconBookmark,
  IconBookmarkFilled,
  IconShare2,
  IconPlayerPlayFilled,
  IconPencil,
  IconAlertTriangle,
} from "@tabler/icons-react";
import { ScenarioDetailResponse } from "../../types/scenario";

interface ScenarioBannerHeroProps {
  scenario: ScenarioDetailResponse;
  isBookmarked: boolean;
  onToggleBookmark: () => void;
  isTogglingBookmark: boolean;
  currentUserId?: string;
}

const playerSupportLabel = (support: string): string => {
  if (support === "both") return "Solo or co-op";
  if (support === "multiplayer") return "Multiplayer";
  return "Solo";
};

export const ScenarioBannerHero: React.FC<ScenarioBannerHeroProps> = ({
  scenario,
  isBookmarked,
  onToggleBookmark,
  isTogglingBookmark,
  currentUserId,
}) => {
  const [copied, setCopied] = useState(false);

  const scenarioId = scenario.scenario_id;
  const genre = scenario.genre_tags[0] || "High Fantasy";
  const coverImage = scenario.cover_image_url || "/images/hero.png";
  const isCreator = Boolean(
    currentUserId && scenario.creator_id === currentUserId,
  );
  const rating = parseFloat(scenario.rating_avg || "0.0").toFixed(1);

  const handleShare = (): void => {
    void navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section className="relative isolate overflow-hidden rounded-2xl border border-border-strong">
      <img
        src={coverImage}
        alt=""
        aria-hidden="true"
        className="absolute inset-0 -z-10 h-full w-full object-cover"
      />
      <div className="absolute inset-0 -z-10 bg-gradient-to-t from-surface-raised via-surface-raised/85 to-surface-raised/40" />
      <div className="absolute inset-0 -z-10 bg-gradient-to-r from-surface-raised/90 to-transparent" />

      <div className="flex flex-col gap-6 p-6 pt-40 md:p-10 md:pt-56">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            {scenario.content_tag && (
              <span className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-warning/40 bg-warning/10 px-2.5 py-1 font-mono text-[11px] font-medium uppercase tracking-wide text-warning">
                <IconAlertTriangle size={12} />
                {scenario.content_tag}
              </span>
            )}

            <h1 className="font-display text-4xl font-bold leading-[1.05] text-content md:text-6xl">
              {scenario.title}
            </h1>

            <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-sm text-content-muted">
              <span className="flex items-center gap-1 text-accent">
                <IconStarFilled size={14} />
                {rating}
              </span>
              <span className="text-content-faint">·</span>
              <span>{genre}</span>
              <span className="text-content-faint">·</span>
              <span className="capitalize">{scenario.mode} mode</span>
              <span className="text-content-faint">·</span>
              <span className="flex items-center gap-1">
                <IconUsers size={14} />
                {playerSupportLabel(scenario.player_count_support)}
              </span>
              {scenario.estimated_playtime && (
                <>
                  <span className="text-content-faint">·</span>
                  <span className="flex items-center gap-1">
                    <IconClock size={14} />
                    {scenario.estimated_playtime}
                  </span>
                </>
              )}
            </div>

            <p className="mt-3 font-sans text-sm text-content-muted">
              by{" "}
              <Link
                to={`/profile/${scenario.creator_id}`}
                className="text-content underline decoration-border-strong underline-offset-4 transition-colors hover:decoration-accent"
              >
                {scenario.creator_display_name || "Anonymous"}
              </Link>
              <span className="mx-2 text-content-faint">·</span>
              {scenario.play_count.toLocaleString()} plays
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <Link
              to={`/setup/${scenarioId}`}
              className="inline-flex items-center gap-2 rounded-full bg-content px-6 py-3 font-sans text-sm font-semibold text-surface transition hover:bg-white active:translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface-raised"
            >
              <IconPlayerPlayFilled size={16} />
              Play now
            </Link>

            {isCreator && (
              <Link
                to={`/studio/${scenarioId}`}
                className="inline-flex items-center gap-2 rounded-full border border-border-strong bg-surface/60 px-4 py-3 font-sans text-sm font-medium text-content-muted backdrop-blur-sm transition hover:text-content"
              >
                <IconPencil size={16} />
                Edit
              </Link>
            )}

            <button
              onClick={onToggleBookmark}
              disabled={isTogglingBookmark}
              aria-label={isBookmarked ? "Remove bookmark" : "Bookmark"}
              className={`flex h-11 w-11 items-center justify-center rounded-full border backdrop-blur-sm transition ${
                isBookmarked
                  ? "border-accent/50 bg-accent/15 text-accent"
                  : "border-border-strong bg-surface/60 text-content-muted hover:text-content"
              }`}
            >
              {isBookmarked ? (
                <IconBookmarkFilled size={18} />
              ) : (
                <IconBookmark size={18} />
              )}
            </button>

            <button
              onClick={handleShare}
              aria-label="Copy link"
              className="flex h-11 items-center gap-2 rounded-full border border-border-strong bg-surface/60 px-4 font-mono text-xs text-content-muted backdrop-blur-sm transition hover:text-content"
            >
              <IconShare2 size={16} />
              {copied ? "Copied" : "Share"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
};
