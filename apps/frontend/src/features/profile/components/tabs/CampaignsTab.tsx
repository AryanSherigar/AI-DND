import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useUserPlaythroughs } from "../../hooks/useUserPlaythroughs";
import { useAbandonPlaythrough } from "../../hooks/useAbandonPlaythrough";
import { CampaignCard } from "../cards/CampaignCard";

type CampaignFilter = "all" | "active" | "completed";

export const CampaignsTab: React.FC = () => {
  const [filter, setFilter] = useState<CampaignFilter>("all");

  const queryStatus = filter === "all" ? undefined : filter;
  const {
    data: campaigns,
    isLoading,
    isError,
  } = useUserPlaythroughs(queryStatus);
  const abandonMutation = useAbandonPlaythrough();

  const handleAbandon = (playthroughId: string) => {
    abandonMutation.mutate(playthroughId);
  };

  if (isLoading) {
    return (
      <div className="py-16 text-center font-mono text-zinc-400">
        Loading campaign chronicles...
      </div>
    );
  }

  if (isError) {
    return (
      <div className="py-16 text-center font-mono text-rose-400">
        Failed to load campaigns from the archives.
      </div>
    );
  }

  const items = campaigns || [];

  return (
    <div className="space-y-6">
      {/* Filter Bar */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 p-1 font-mono text-xs">
          <button
            onClick={() => setFilter("all")}
            className={`rounded-md px-3 py-1.5 transition-all ${
              filter === "all"
                ? "bg-amber-500/20 text-amber-300 font-bold shadow"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            All Campaigns
          </button>
          <button
            onClick={() => setFilter("active")}
            className={`rounded-md px-3 py-1.5 transition-all ${
              filter === "active"
                ? "bg-amber-500/20 text-amber-300 font-bold shadow"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            Active
          </button>
          <button
            onClick={() => setFilter("completed")}
            className={`rounded-md px-3 py-1.5 transition-all ${
              filter === "completed"
                ? "bg-amber-500/20 text-amber-300 font-bold shadow"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            Completed
          </button>
        </div>

        <Link
          to="/discover"
          className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-zinc-950 font-mono text-xs font-bold transition-all shadow"
        >
          ⚔️ Start New Adventure
        </Link>
      </div>

      {/* Campaigns List */}
      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-800 p-12 text-center">
          <p className="font-serif italic text-zinc-400 mb-4">
            {filter === "active"
              ? "You have no active campaigns at this time."
              : filter === "completed"
                ? "No completed adventures recorded in your chronicle yet."
                : "You have not embarked on any campaigns yet."}
          </p>
          <Link
            to="/discover"
            className="text-amber-400 font-mono text-xs hover:underline"
          >
            Explore scenarios in the tavern feed →
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((campaign) => (
            <CampaignCard
              key={campaign.playthrough_id}
              campaign={campaign}
              onAbandon={handleAbandon}
              isAbandoning={abandonMutation.isPending}
            />
          ))}
        </div>
      )}
    </div>
  );
};
