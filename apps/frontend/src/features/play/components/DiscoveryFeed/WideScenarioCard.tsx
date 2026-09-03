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

  const cardContainerStyle = isHovered
    ? {
        backgroundColor: `${accentColor}18`,
        borderColor: `${accentColor}70`,
        boxShadow: `0 8px 30px ${accentColor}35, 0 0 15px ${accentColor}20`,
      }
    : {
        backgroundColor: "transparent",
        borderColor: "transparent",
      };

  return (
    <div
      onClick={handleCardClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={cardContainerStyle}
      className="flex flex-col md:flex-row gap-4 md:gap-8 group p-3 md:p-4 rounded-2xl border transition-all duration-300 cursor-pointer"
    >
      {/* 16:9 Thumbnail Area */}
      <div
        className="relative w-full md:w-80 lg:w-96 flex-shrink-0 aspect-video rounded-xl overflow-hidden border transition-colors bg-[#0d0f14]"
        style={{
          borderColor: isHovered ? `${accentColor}80` : "rgba(39, 39, 42, 0.8)",
        }}
      >
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
            className="flex items-center justify-center w-12 h-12 bg-emerald-500 hover:bg-emerald-400 text-white rounded-full shadow-lg transition-transform transform hover:scale-110"
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
          <h2 className="text-2xl md:text-3xl lg:text-4xl font-fell-sc font-bold text-white group-hover:text-emerald-400 transition-colors truncate">
            {title}
          </h2>
          <button className="text-zinc-500 hover:text-white p-1">
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
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-sm font-mono text-zinc-400">
          <span className="flex items-center gap-1.5 text-zinc-300">
            <UserIcon className="w-4 h-4 opacity-70" />
            {author}
          </span>
          <span className="hidden md:inline text-zinc-600">•</span>
          <span>{playerCount.toLocaleString()} plays</span>
          <span className="hidden md:inline text-zinc-600">•</span>
          <span className="flex items-center text-yellow-500/90 gap-1">
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
          <span className="hidden md:inline text-zinc-600">•</span>
          <span
            className="px-2 py-0.5 rounded-md text-zinc-950 text-[11px] font-bold shadow-md capitalize"
            style={{
              backgroundColor: accentColor,
            }}
          >
            {genre}
          </span>
        </div>

        {/* Creator Description / Logline */}
        <p className="mt-3 text-sm text-zinc-400 leading-relaxed font-sans line-clamp-2 md:line-clamp-3">
          {logline}
        </p>

        {/* Bottom tags */}
        <div className="mt-auto pt-4 flex gap-2">
          <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 text-xs font-mono">
            {modeBadge}
          </span>
          <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 text-xs font-mono">
            {playerSupportBadge}
          </span>
        </div>
      </div>
    </div>
  );
};
