import React, { useState } from "react";
import { Link } from "react-router-dom";
import { ScenarioDetailResponse, GENRE_COLORS } from "../../types/scenario";
import {
  HeartIcon,
  PlayersIcon,
  QuillIcon,
} from "../../../../shared/components/icons/CleanIcons";

interface ScenarioBannerHeroProps {
  scenario: ScenarioDetailResponse;
  isBookmarked: boolean;
  onToggleBookmark: () => void;
  isTogglingBookmark: boolean;
  currentUserId?: string;
}

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
  const accentColor = GENRE_COLORS[genre] || "#D4AF6A";
  const coverImage = scenario.cover_image_url || "/images/hero.png";

  const isCreator = Boolean(
    currentUserId && scenario.creator_id === currentUserId,
  );

  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const ratingVal = parseFloat(scenario.rating_avg || "0.0").toFixed(1);

  return (
    <div className="relative w-full overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950 shadow-2xl">
      {/* Banner Cover Image */}
      <div className="relative aspect-[21/9] w-full overflow-hidden md:aspect-[24/9]">
        <img
          src={coverImage}
          alt={scenario.title}
          className="h-full w-full object-cover opacity-85 transition-scale duration-700 hover:scale-105"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/40 to-transparent" />
        <div className="absolute inset-0 bg-gradient-to-r from-zinc-950/80 via-transparent to-zinc-950/80" />

        {/* Top-Right Advisory Tag */}
        {scenario.content_tag && (
          <div className="absolute top-4 right-4 z-10 rounded-md border border-amber-500/30 bg-zinc-950/80 px-3 py-1 font-mono text-xs font-bold text-amber-400 backdrop-blur-md shadow-lg">
            ⚠️ {scenario.content_tag}
          </div>
        )}
      </div>

      {/* Main Metadata Content Area */}
      <div className="relative z-10 -mt-16 px-6 pb-8 md:-mt-24 md:px-10">
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div className="space-y-3 max-w-3xl">
            {/* Genre & Mode Badges */}
            <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
              <span
                className="rounded-md px-2.5 py-1 font-bold text-zinc-950 shadow-sm"
                style={{ backgroundColor: accentColor }}
              >
                {genre}
              </span>
              <span className="rounded-md border border-zinc-800 bg-zinc-900 px-2.5 py-1 text-zinc-300 capitalize">
                {scenario.mode} Mode
              </span>
              <span className="rounded-md border border-zinc-800 bg-zinc-900 px-2.5 py-1 text-zinc-300 capitalize">
                {scenario.player_count_support === "both"
                  ? "Solo / Co-op"
                  : scenario.player_count_support}
              </span>
              {scenario.estimated_playtime && (
                <span className="rounded-md border border-zinc-800 bg-zinc-900 px-2.5 py-1 text-zinc-400">
                  ⏱️ {scenario.estimated_playtime}
                </span>
              )}
            </div>

            {/* Scenario Title */}
            <h1 className="font-fell-sc text-3xl font-extrabold text-white md:text-5xl drop-shadow-md leading-tight">
              {scenario.title}
            </h1>

            {/* Creator info & Quick stats */}
            <div className="flex flex-wrap items-center gap-4 text-sm text-zinc-400 font-mono">
              <span className="flex items-center gap-1.5 text-zinc-200">
                <QuillIcon className="h-4 w-4 text-emerald-400" />
                <span>
                  {scenario.creator_display_name || "Anonymous Creator"}
                </span>
              </span>
              <span className="text-zinc-700">•</span>
              <span className="flex items-center gap-1 text-yellow-500">
                <HeartIcon className="h-4 w-4" />
                <span className="font-bold">{ratingVal}</span>
              </span>
              <span className="text-zinc-700">•</span>
              <span className="flex items-center gap-1.5 text-zinc-300">
                <PlayersIcon className="h-4 w-4 text-zinc-400" />
                <span>{scenario.play_count.toLocaleString()} plays</span>
              </span>
            </div>
          </div>

          {/* Action Button Bar */}
          <div className="flex flex-wrap items-center gap-3 pt-2 md:pt-0 shrink-0">
            <Link
              to={`/setup/${scenarioId}`}
              className="flex items-center gap-2 rounded-xl bg-emerald-500 px-6 py-3.5 font-sans font-bold text-zinc-950 shadow-lg shadow-emerald-500/20 transition-all hover:bg-emerald-400 hover:scale-105 active:scale-95"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <polygon points="5 3 19 12 5 21 5 3"></polygon>
              </svg>
              <span>Begin Adventure</span>
            </Link>

            {isCreator && (
              <Link
                to={`/studio/${scenarioId}`}
                className="flex items-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-5 py-3.5 font-sans font-semibold text-amber-300 hover:bg-amber-500/20 transition-colors"
              >
                ✏️ Edit in Studio
              </Link>
            )}

            <button
              onClick={onToggleBookmark}
              disabled={isTogglingBookmark}
              className={`flex items-center justify-center rounded-xl border p-3.5 transition-colors ${
                isBookmarked
                  ? "border-emerald-500/50 bg-emerald-500/20 text-emerald-400"
                  : "border-zinc-800 bg-zinc-900 text-zinc-400 hover:text-white"
              }`}
              title={isBookmarked ? "Remove Bookmark" : "Bookmark Scenario"}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill={isBookmarked ? "currentColor" : "none"}
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>
              </svg>
            </button>

            <button
              onClick={handleShare}
              className="flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3.5 font-mono text-sm text-zinc-300 hover:bg-zinc-800 transition-colors relative"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="18" cy="5" r="3"></circle>
                <circle cx="6" cy="12" r="3"></circle>
                <circle cx="18" cy="19" r="3"></circle>
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
              </svg>
              <span>{copied ? "Copied!" : "Share"}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
