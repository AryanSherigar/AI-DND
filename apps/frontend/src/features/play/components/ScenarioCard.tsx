import React, { useState } from "react";
import { ScenarioCardProps } from "./ScenarioCard.types";
import { GENRE_COLORS } from "../types/scenario";
import {
  HeartIcon,
  PlayersIcon,
  QuillIcon,
} from "../../../shared/components/icons/CleanIcons";

const DEFAULT_ACCENT_COLOR = "#6B7280";

interface SubComponentProps {
  scenario: ScenarioCardProps["scenario"];
  accentColor: string;
}

const CardThumbnail: React.FC<SubComponentProps> = ({
  scenario,
  accentColor,
}) => {
  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-xl border border-white/10 bg-zinc-900">
      <img
        src={scenario.coverImageUrl}
        alt={scenario.title}
        className="h-full w-full object-cover"
      />
      <div className="absolute inset-0 bg-gradient-to-t from-zinc-950/80 via-transparent to-transparent opacity-60" />

      {/* Top-Left Genre Pill */}
      <div className="absolute top-2.5 left-2.5 z-10">
        <span
          className="rounded-md px-2 py-0.5 font-mono text-[11px] font-bold text-zinc-950 shadow-md backdrop-blur-md"
          style={{ backgroundColor: accentColor }}
        >
          {scenario.genre}
        </span>
      </div>

      {/* Bottom-Right Rating & Players Badge */}
      <div className="absolute bottom-2.5 right-2.5 z-10 flex items-center gap-2 rounded-md bg-zinc-950/85 px-2 py-0.5 font-mono text-xs font-medium text-white shadow-lg backdrop-blur-md border border-white/10">
        <span
          className="flex items-center gap-1"
          style={{ color: accentColor }}
        >
          <HeartIcon className="h-3.5 w-3.5" />
          <span className="text-zinc-200">{scenario.rating}</span>
        </span>
        <span className="text-zinc-600">•</span>
        <span className="flex items-center gap-1 text-zinc-300">
          <PlayersIcon className="h-3.5 w-3.5 text-zinc-400" />
          <span>{scenario.playerCount}</span>
        </span>
      </div>
    </div>
  );
};

const AuthorAvatar: React.FC<{ author: string; accentColor: string }> = ({
  author,
  accentColor,
}) => {
  const authorInitial = author ? author.charAt(0).toUpperCase() : "?";

  return (
    <div
      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-zinc-900 font-mono text-xs font-bold text-white shadow-inner border transition-colors duration-300"
      style={{ borderColor: `${accentColor}80` }}
    >
      {authorInitial}
    </div>
  );
};

const CardMetadata: React.FC<SubComponentProps> = ({ scenario }) => {
  return (
    <div className="flex-1 min-w-0">
      <h3 className="font-fell-sc text-base font-bold text-white line-clamp-2 leading-snug drop-shadow-xs">
        {scenario.title}
      </h3>
      <div className="mt-1 flex items-center gap-2 font-mono text-xs text-zinc-400">
        <span className="flex items-center gap-1 text-zinc-300 line-clamp-1">
          <QuillIcon className="h-3 w-3 text-zinc-500" />
          {scenario.author}
        </span>
      </div>
    </div>
  );
};

export const ScenarioCard: React.FC<ScenarioCardProps> = ({
  scenario,
  isDimmed = false,
  onHoverStart,
  onHoverEnd,
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const accentColor = GENRE_COLORS[scenario.genre] || DEFAULT_ACCENT_COLOR;

  const handleMouseEnter = () => {
    setIsHovered(true);
    if (onHoverStart) onHoverStart();
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    if (onHoverEnd) onHoverEnd();
  };

  const dimmedClass = isDimmed ? "opacity-40 blur-[0.5px]" : "opacity-100";

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
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={cardContainerStyle}
      className={`group relative flex flex-col gap-0 w-full p-2 rounded-2xl border transition-all duration-300 cursor-pointer ${dimmedClass}`}
    >
      <CardThumbnail scenario={scenario} accentColor={accentColor} />
      <div className="flex items-start gap-2.5 px-0.5 pt-1">
        <AuthorAvatar author={scenario.author} accentColor={accentColor} />
        <CardMetadata scenario={scenario} accentColor={accentColor} />
      </div>
    </div>
  );
};
