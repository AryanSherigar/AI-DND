import React from "react";
import { ScenarioMock, GENRE_COLORS } from "../types/scenario";
import {
  HeartIcon,
  TextInputIcon,
  QuillIcon,
  PlayIcon,
} from "../../../shared/components/icons/PixelIcons";

interface ScenarioCardProps {
  scenario: ScenarioMock;
}

export const ScenarioCard: React.FC<ScenarioCardProps> = ({ scenario }) => {
  const accentColor = GENRE_COLORS[scenario.genre] || "#6B7280";

  return (
    <div
      className="group/card relative flex-none w-72 md:w-80 aspect-[3/4] overflow-hidden cursor-pointer transition-all duration-300 hover:scale-[1.03] hover:z-10 bg-[#0d0f14]"
      style={{
        clipPath:
          "polygon(20px 0, 100% 0, 100% calc(100% - 20px), calc(100% - 20px) 100%, 0 100%, 0 20px)",
      }}
    >
      {/* Dynamic Inset Border */}
      <div
        className="absolute inset-[1px] z-20 pointer-events-none opacity-50 group-hover/card:opacity-100 transition-opacity duration-300"
        style={{
          border: `1px solid ${accentColor}`,
          clipPath:
            "polygon(19px 0, 100% 0, 100% calc(100% - 19px), calc(100% - 19px) 100%, 0 100%, 0 19px)",
        }}
      />

      {/* Cover Image */}
      <img
        src={scenario.coverImageUrl}
        alt={scenario.title}
        className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 ease-out group-hover/card:scale-110 opacity-70 group-hover/card:opacity-40"
      />

      {/* Gradient overlay always present but deepens on hover */}
      <div className="absolute inset-0 bg-gradient-to-t from-[#0d0f14] via-[#0d0f14]/50 to-transparent opacity-90 transition-opacity duration-300" />

      {/* Content Container */}
      <div className="absolute inset-0 p-5 flex flex-col justify-end z-30">
        {/* Default visible info */}
        <div className="transition-all duration-300 ease-in-out group-hover/card:-translate-y-8 group-hover/card:opacity-0 group-hover/card:invisible">
          <h3 className="font-fell-sc font-bold text-xl text-white mb-2 line-clamp-2 leading-snug drop-shadow-md">
            {scenario.title}
          </h3>
          <div className="flex items-center justify-between text-sm text-zinc-300 font-mono font-medium">
            <span
              className="flex items-center gap-1.5"
              style={{ color: accentColor }}
            >
              <HeartIcon className="w-4 h-4" />{" "}
              <span className="text-zinc-300">{scenario.rating}</span>
            </span>
            <span
              className="flex items-center gap-1.5"
              style={{ color: accentColor }}
            >
              <TextInputIcon className="w-4 h-4" />{" "}
              <span className="text-zinc-300">{scenario.playerCount}</span>
            </span>
          </div>
        </div>

        {/* Info revealed on hover */}
        <div className="absolute bottom-0 left-0 right-0 p-5 opacity-0 translate-y-8 group-hover/card:opacity-100 group-hover/card:translate-y-0 transition-all duration-300 ease-out pointer-events-none group-hover/card:pointer-events-auto">
          <h3 className="font-fell-sc font-bold text-lg text-white mb-2 line-clamp-2 leading-tight drop-shadow-md">
            {scenario.title}
          </h3>
          <p className="font-fell text-sm text-zinc-300 line-clamp-3 mb-4 leading-relaxed">
            {scenario.logline || "No description provided."}
          </p>
          <div className="pt-3 border-t border-white/10 mt-1">
            <div className="flex justify-between items-center mb-4 font-mono text-xs font-semibold tracking-wider">
              <span style={{ color: accentColor }}>{scenario.genre}</span>
              <span className="flex items-center gap-1 text-zinc-400 font-mono">
                <QuillIcon className="w-3 h-3" /> {scenario.author}
              </span>
            </div>
            <button
              className="flex justify-center items-center gap-2 w-full bg-white text-zinc-950 font-mono font-bold text-sm py-2 hover:bg-zinc-200 transition-colors"
              style={{
                clipPath:
                  "polygon(8px 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%, 0 8px)",
              }}
            >
              <PlayIcon className="w-4 h-4" /> PLAY
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
