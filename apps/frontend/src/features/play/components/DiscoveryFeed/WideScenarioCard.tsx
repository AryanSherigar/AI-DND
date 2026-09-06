import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { GENRE_COLORS } from "../../types/scenario";
import { DisplayScenario } from "../../hooks/useDiscovery";
import { UserIcon } from "../../../../shared/components/icons/PixelIcons";

interface WideScenarioCardProps {
  scenario: DisplayScenario;
}

export const WideScenarioCard: React.FC<WideScenarioCardProps> = ({
  scenario,
}) => {
  const navigate = useNavigate();
  const [isHovered, setIsHovered] = useState(false);

  const scenarioId =
    "scenario_id" in scenario ? scenario.scenario_id : scenario.id;

  const handleCardClick = () => {
    navigate(`/scenario/${scenarioId}`);
  };
  const title = scenario.title;
  const logline = scenario.logline || "No description provided.";
  const author =
    "author" in scenario
      ? scenario.author
      : scenario.creator_id
        ? `Creator #${scenario.creator_id.substring(0, 8)}`
        : "Anonymous Creator";
  const playerCount =
    "play_count" in scenario
      ? scenario.play_count
      : (scenario.playerCount ?? 0);
  const rating =
    "rating_avg" in scenario
      ? parseFloat(scenario.rating_avg || "0.0")
      : (scenario.rating ?? 0);
  const genre =
    "genre_tags" in scenario
      ? scenario.genre_tags[0] || "Fantasy"
      : scenario.genre || "High Fantasy";
  const modeBadge =
    "mode" in scenario
      ? scenario.mode === "master"
        ? "Master Mode"
        : "Newbie Mode"
      : "Newbie Mode";
  const playerSupportBadge =
    "player_count_support" in scenario
      ? scenario.player_count_support === "multiplayer"
        ? "Multiplayer"
        : scenario.player_count_support === "both"
          ? "Solo / Co-op"
          : "Solo"
      : "Solo";
  const coverImageUrl =
    ("cover_image_url" in scenario
      ? scenario.cover_image_url
      : scenario.coverImageUrl) || "/images/hero.png";

  const accentColor = GENRE_COLORS[genre] || "#6B7280";

  return (
    <div
      onClick={handleCardClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={`group flex cursor-pointer flex-col gap-4 rounded-xl border p-3 transition-colors duration-200 md:flex-row md:gap-8 md:p-4 ${
        isHovered
          ? "border-border-strong bg-surface-overlay"
          : "border-transparent bg-transparent"
      }`}
    >
      {/* 16:9 Thumbnail Area */}
      <div className="relative aspect-video w-full flex-shrink-0 overflow-hidden rounded-lg border border-border-subtle bg-surface-inset transition-colors md:w-80 lg:w-96">
        <img
          src={coverImageUrl}
          alt={title}
          className="w-full h-full object-cover transform group-hover:scale-105 transition-transform duration-500 ease-out"
        />
        {/* Play Button Overlay */}
        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          <Link
            to={`/setup/${scenarioId}`}
            onClick={(e) => e.stopPropagation()}
            className="flex h-12 w-12 items-center justify-center rounded-full bg-accent text-accent-contrast shadow-lg transition-transform hover:scale-110"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="currentColor"
              className="ml-1"
            >
              <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
          </Link>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex flex-col py-1 flex-1 min-w-0 md:justify-center">
        <div className="flex justify-between items-start gap-4">
          <h2 className="truncate font-fell-sc text-2xl font-bold text-content transition-colors group-hover:text-accent md:text-3xl lg:text-4xl">
            {title}
          </h2>
          <button className="p-1 text-content-faint hover:text-content">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="1"></circle>
              <circle cx="12" cy="5" r="1"></circle>
              <circle cx="12" cy="19" r="1"></circle>
            </svg>
          </button>
        </div>

        {/* Metadata Row */}
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-sm text-content-faint">
          {"creator_id" in scenario && scenario.creator_id ? (
            <Link
              to={`/profile/${scenario.creator_id}`}
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1.5 text-content-muted transition-colors hover:text-accent"
            >
              <UserIcon className="h-4 w-4 opacity-70" />
              <span className="hover:underline">{author}</span>
            </Link>
          ) : (
            <span className="flex items-center gap-1.5 text-content-muted">
              <UserIcon className="h-4 w-4 opacity-70" />
              {author}
            </span>
          )}
          <span className="hidden text-content-faint md:inline">•</span>
          <span>{playerCount.toLocaleString()} plays</span>
          <span className="hidden text-content-faint md:inline">•</span>
          <span className="flex items-center gap-1 text-warning">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="currentColor"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
            </svg>
            {rating.toFixed(1)}
          </span>
          <span className="hidden text-content-faint md:inline">•</span>
          <span
            className="rounded-sm px-2 py-0.5 text-[11px] font-bold capitalize text-neutral-950"
            style={{ backgroundColor: accentColor }}
          >
            {genre}
          </span>
        </div>

        {/* Creator Description / Logline */}
        <p className="mt-3 line-clamp-2 font-sans text-sm leading-relaxed text-content-muted md:line-clamp-3">
          {logline}
        </p>

        {/* Bottom tags */}
        <div className="mt-auto flex gap-2 pt-4">
          <span className="rounded-sm bg-surface px-2 py-0.5 font-mono text-xs text-content-muted">
            {modeBadge}
          </span>
          <span className="rounded-sm bg-surface px-2 py-0.5 font-mono text-xs text-content-muted">
            {playerSupportBadge}
          </span>
        </div>
      </div>
    </div>
  );
};
