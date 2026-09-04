import React from "react";
import { UserStats } from "../types/profile.types";

export interface ProfileStatsRibbonProps {
  stats: UserStats;
}

interface StatItem {
  id: string;
  label: string;
  value: number;
  icon: string;
  color: string;
}

export const ProfileStatsRibbon: React.FC<ProfileStatsRibbonProps> = ({
  stats,
}) => {
  const statItems: StatItem[] = [
    {
      id: "campaigns",
      label: "Campaigns",
      value: stats.campaigns_played_count,
      icon: "⚔️",
      color: "text-amber-400",
    },
    {
      id: "victories",
      label: "Victories",
      value: stats.victories_count,
      icon: "🏆",
      color: "text-emerald-400",
    },
    {
      id: "turns",
      label: "Turns Taken",
      value: stats.total_turns_taken,
      icon: "📜",
      color: "text-cyan-400",
    },
    {
      id: "authored",
      label: "Authored",
      value: stats.scenarios_authored_count,
      icon: "✒️",
      color: "text-purple-400",
    },
    {
      id: "plays",
      label: "Plays Received",
      value: stats.total_plays_received,
      icon: "👥",
      color: "text-yellow-400",
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 w-full">
      {statItems.map((item) => (
        <div
          key={item.id}
          className="relative overflow-hidden rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-3.5 backdrop-blur-md transition-all hover:border-amber-500/40 hover:bg-zinc-900/90 shadow-lg group"
        >
          <div className="flex items-center justify-between">
            <span className="text-xl select-none group-hover:scale-110 transition-transform">
              {item.icon}
            </span>
            <span className={`font-mono text-2xl font-bold ${item.color}`}>
              {item.value.toLocaleString()}
            </span>
          </div>
          <div className="mt-2 font-mono text-[11px] uppercase tracking-wider text-zinc-400">
            {item.label}
          </div>
        </div>
      ))}
    </div>
  );
};
