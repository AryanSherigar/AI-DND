import React, { useState } from "react";
import { Link } from "react-router-dom";
import { UserPlaythroughSummary } from "../../types/profile.types";
import { GENRE_COLORS } from "@/features/play/types/scenario";

export interface CampaignCardProps {
  campaign: UserPlaythroughSummary;
  onAbandon: (playthroughId: string) => void;
  isAbandoning?: boolean;
}

export const CampaignCard: React.FC<CampaignCardProps> = ({
  campaign,
  onAbandon,
  isAbandoning = false,
}) => {
  const [showConfirmAbandon, setShowConfirmAbandon] = useState(false);

  const coverImage = campaign.cover_image_url || "/images/hero.png";
  const isWin = campaign.ended_outcome_tag === "win";
  const isCompleted = campaign.status === "completed";
  const isActive = campaign.status === "active";
  const isAbandoned = campaign.status === "abandoned";

  const handleAbandonClick = () => {
    setShowConfirmAbandon(true);
  };

  const handleConfirmAbandon = () => {
    onAbandon(campaign.playthrough_id);
    setShowConfirmAbandon(false);
  };

  const handleCancelAbandon = () => {
    setShowConfirmAbandon(false);
  };

  return (
    <div className="relative flex flex-col sm:flex-row overflow-hidden rounded-xl border border-zinc-800/80 bg-zinc-900/60 transition-all hover:border-amber-500/40 hover:bg-zinc-900/90 shadow-lg group">
      {/* Cover Thumbnail */}
      <div className="relative w-full sm:w-48 sm:min-w-[12rem] h-36 sm:h-auto overflow-hidden shrink-0">
        <img
          src={coverImage}
          alt={campaign.scenario_title}
          className="h-full w-full object-cover opacity-80 group-hover:scale-105 transition-transform duration-500"
        />
        <div className="absolute inset-0 bg-gradient-to-t sm:bg-gradient-to-r from-transparent to-zinc-900/90" />

        {/* Mode Badge */}
        <span
          className="absolute top-3 left-3 rounded-md px-2 py-0.5 font-mono text-[10px] font-bold text-zinc-950 uppercase"
          style={{ backgroundColor: GENRE_COLORS["High Fantasy"] }}
        >
          {campaign.scenario_mode} Mode
        </span>
      </div>

      {/* Campaign Details */}
      <div className="flex flex-col justify-between p-4 sm:p-5 flex-grow space-y-3">
        <div>
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <h3 className="font-fell-sc text-xl font-bold text-white group-hover:text-amber-300 transition-colors">
              {campaign.scenario_title}
            </h3>

            {/* Status Pill */}
            {isActive && (
              <span className="flex items-center gap-1.5 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-0.5 font-mono text-xs font-bold text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Active Run
              </span>
            )}
            {isCompleted && (
              <span
                className={`rounded-full border px-2.5 py-0.5 font-mono text-xs font-bold ${
                  isWin
                    ? "border-amber-500/40 bg-amber-500/10 text-amber-300"
                    : "border-rose-500/40 bg-rose-500/10 text-rose-400"
                }`}
              >
                {isWin ? "🏆 Victory" : "💀 Defeat"}
              </span>
            )}
            {isAbandoned && (
              <span className="rounded-full border border-zinc-700 bg-zinc-800/60 px-2.5 py-0.5 font-mono text-xs text-zinc-400">
                Abandoned
              </span>
            )}
          </div>

          {/* Character and Turn info */}
          <div className="mt-2 flex flex-wrap items-center gap-3 font-mono text-xs text-zinc-400">
            {(campaign.character_name || campaign.character_archetype) && (
              <span className="text-zinc-200">
                👤 {campaign.character_name || "Hero"}{" "}
                {campaign.character_archetype &&
                  `(${campaign.character_archetype})`}
              </span>
            )}
            <span>•</span>
            <span>📜 Turn {campaign.turn_count}</span>
          </div>

          {/* Completed ending snippet */}
          {isCompleted && campaign.ended_outcome_title && (
            <p className="mt-2 font-serif italic text-xs text-zinc-300 line-clamp-1">
              &ldquo;{campaign.ended_outcome_title}&rdquo;
            </p>
          )}
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-zinc-800/60">
          <div className="flex items-center gap-2">
            {isActive ? (
              <Link
                to={`/play/${campaign.playthrough_id}`}
                className="px-4 py-1.5 rounded-md bg-amber-500 hover:bg-amber-400 text-zinc-950 font-mono text-xs font-bold shadow transition-all"
              >
                Resume Run
              </Link>
            ) : (
              <Link
                to={`/play/${campaign.playthrough_id}`}
                className="px-4 py-1.5 rounded-md border border-zinc-700 hover:border-zinc-500 text-zinc-300 font-mono text-xs transition-colors"
              >
                View Chronicle
              </Link>
            )}

            {isCompleted && (
              <Link
                to={`/scenario/${campaign.scenario_id}`}
                className="px-3 py-1.5 rounded-md border border-amber-500/30 hover:border-amber-500/60 text-amber-300 font-mono text-xs transition-colors"
              >
                Review Scenario
              </Link>
            )}
          </div>

          {isActive && (
            <div>
              {showConfirmAbandon ? (
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-rose-400">
                    Abandon run?
                  </span>
                  <button
                    onClick={handleConfirmAbandon}
                    disabled={isAbandoning}
                    className="px-2.5 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white font-mono text-xs font-bold"
                  >
                    Yes
                  </button>
                  <button
                    onClick={handleCancelAbandon}
                    className="px-2 py-1 rounded border border-zinc-700 text-zinc-400 font-mono text-xs hover:text-white"
                  >
                    No
                  </button>
                </div>
              ) : (
                <button
                  onClick={handleAbandonClick}
                  className="font-mono text-xs text-zinc-500 hover:text-rose-400 transition-colors"
                >
                  Abandon
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
