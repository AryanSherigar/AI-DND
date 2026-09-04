import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchScenarios } from "@/features/play/api/discovery.api";
import {
  ScenarioSummaryResponse,
  GENRE_COLORS,
} from "@/features/play/types/scenario";

export interface CreationsTabProps {
  userId: string;
  isOwner: boolean;
}

export const CreationsTab: React.FC<CreationsTabProps> = ({
  userId,
  isOwner,
}) => {
  const [subTab, setSubTab] = useState<"published" | "drafts">("published");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["profile-creations", userId, isOwner ? "mine" : "public"],
    queryFn: () =>
      fetchScenarios(isOwner ? { mine: true } : { creator_id: userId }),
  });

  const allItems = data?.items || [];
  const items = isOwner
    ? allItems.filter((scen) =>
        subTab === "published"
          ? scen.status === "published"
          : scen.status !== "published",
      )
    : allItems.filter((scen) => scen.status === "published");

  if (isLoading) {
    return (
      <div className="py-16 text-center font-mono text-zinc-400">
        Consulting the realm archives...
      </div>
    );
  }

  if (isError) {
    return (
      <div className="py-16 text-center font-mono text-rose-400">
        Failed to retrieve authored creations.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Owner Sub-Tabs and Actions */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        {isOwner ? (
          <div className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 p-1 font-mono text-xs">
            <button
              onClick={() => setSubTab("published")}
              className={`rounded-md px-3 py-1.5 transition-all ${
                subTab === "published"
                  ? "bg-amber-500/20 text-amber-300 font-bold shadow"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              Published (
              {allItems.filter((s) => s.status === "published").length})
            </button>
            <button
              onClick={() => setSubTab("drafts")}
              className={`rounded-md px-3 py-1.5 transition-all ${
                subTab === "drafts"
                  ? "bg-amber-500/20 text-amber-300 font-bold shadow"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              Drafts & In-Progress (
              {allItems.filter((s) => s.status !== "published").length})
            </button>
          </div>
        ) : (
          <div className="font-mono text-xs uppercase tracking-wider text-zinc-400">
            Published Creations ({items.length})
          </div>
        )}

        {isOwner && (
          <Link
            to="/studio/new"
            className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-zinc-950 font-mono text-xs font-bold transition-all shadow"
          >
            + Author New Scenario
          </Link>
        )}
      </div>

      {/* Scenarios Grid */}
      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-800 p-12 text-center">
          <p className="font-serif italic text-zinc-400 mb-4">
            {isOwner
              ? subTab === "published"
                ? "You have not published any scenarios to the realm yet."
                : "No draft scenarios currently in authoring."
              : "This adventurer has not published any public scenarios yet."}
          </p>
          {isOwner && subTab === "published" && (
            <Link
              to="/studio"
              className="text-amber-400 font-mono text-xs hover:underline"
            >
              Open Studio to publish a draft →
            </Link>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {items.map((scenario: ScenarioSummaryResponse) => {
            const genre = scenario.genre_tags[0] || "High Fantasy";
            const accentColor = GENRE_COLORS[genre] || "#D4AF6A";
            const cover = scenario.cover_image_url || "/images/hero.png";

            return (
              <div
                key={scenario.scenario_id}
                className="group flex flex-col overflow-hidden rounded-xl border border-zinc-800/80 bg-zinc-900/60 transition-all hover:border-amber-500/40 hover:bg-zinc-900 shadow-lg"
              >
                <div className="relative aspect-[16/9] w-full overflow-hidden">
                  <img
                    src={cover}
                    alt={scenario.title}
                    className="h-full w-full object-cover opacity-80 group-hover:scale-105 transition-transform duration-500"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-transparent to-transparent" />
                  <span
                    className="absolute top-3 left-3 rounded-md px-2 py-0.5 font-mono text-[10px] font-bold text-zinc-950 uppercase"
                    style={{ backgroundColor: accentColor }}
                  >
                    {genre}
                  </span>
                  <span className="absolute top-3 right-3 rounded-md border border-zinc-800 bg-zinc-950/80 px-2 py-0.5 font-mono text-[10px] text-zinc-300 capitalize">
                    {scenario.mode}
                  </span>
                </div>

                <div className="flex flex-col justify-between p-4 flex-grow space-y-3">
                  <div>
                    <h4 className="font-fell-sc text-lg font-bold text-white group-hover:text-amber-300 transition-colors line-clamp-1">
                      {scenario.title}
                    </h4>
                    {scenario.logline && (
                      <p className="mt-1 font-serif italic text-xs text-zinc-400 line-clamp-2">
                        {scenario.logline}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center justify-between font-mono text-xs text-zinc-400 pt-2 border-t border-zinc-800">
                    <div className="flex items-center gap-3">
                      <span>
                        ★ {parseFloat(scenario.rating_avg).toFixed(1)}
                      </span>
                      <span>👥 {scenario.play_count}</span>
                    </div>

                    <div className="flex items-center gap-2">
                      {isOwner && scenario.status !== "published" && (
                        <Link
                          to={`/studio/${scenario.scenario_id}/edit`}
                          className="px-3 py-1 rounded border border-amber-500/40 text-amber-300 font-mono text-xs hover:bg-amber-500/10 transition-colors"
                        >
                          Edit Draft
                        </Link>
                      )}
                      {scenario.status === "published" && (
                        <Link
                          to={`/scenario/${scenario.scenario_id}`}
                          className="px-3 py-1 rounded bg-amber-500/20 text-amber-300 font-mono text-xs hover:bg-amber-500/30 transition-colors"
                        >
                          View Details
                        </Link>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
