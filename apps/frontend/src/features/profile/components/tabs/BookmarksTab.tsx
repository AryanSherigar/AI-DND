import React from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchScenarios } from "@/features/play/api/discovery.api";
import { toggleBookmarkApi } from "@/features/play/api/scenarioFocus.api";
import {
  ScenarioSummaryResponse,
  GENRE_COLORS,
} from "@/features/play/types/scenario";

export const BookmarksTab: React.FC = () => {
  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["profile-bookmarks"],
    queryFn: () => fetchScenarios({ saved: true, mine: true }),
  });

  const toggleMutation = useMutation({
    mutationFn: (scenarioId: string) => toggleBookmarkApi(scenarioId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile-bookmarks"] });
    },
  });

  if (isLoading) {
    return (
      <div className="py-16 text-center font-mono text-zinc-400">
        Retrieving your saved scrolls...
      </div>
    );
  }

  if (isError) {
    return (
      <div className="py-16 text-center font-mono text-rose-400">
        Failed to load bookmarked scenarios.
      </div>
    );
  }

  const items = data?.items || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="font-mono text-xs uppercase tracking-wider text-zinc-400">
          Saved Scenarios ({items.length})
        </div>
        <Link
          to="/discover"
          className="text-amber-400 font-mono text-xs hover:underline"
        >
          Discover more tales →
        </Link>
      </div>

      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-800 p-12 text-center">
          <p className="font-serif italic text-zinc-400 mb-4">
            You haven't bookmarked any scenarios to your chronicle yet.
          </p>
          <Link
            to="/discover"
            className="text-amber-400 font-mono text-xs hover:underline"
          >
            Explore the discovery feed to bookmark scenarios →
          </Link>
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
                  <button
                    onClick={() => toggleMutation.mutate(scenario.scenario_id)}
                    aria-label="Remove bookmark"
                    className="absolute top-3 right-3 rounded-full bg-zinc-950/80 p-1.5 text-rose-400 hover:text-rose-300 transition-colors shadow"
                  >
                    ✕
                  </button>
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
                    <span>★ {parseFloat(scenario.rating_avg).toFixed(1)}</span>
                    <Link
                      to={`/setup/${scenario.scenario_id}`}
                      className="px-3 py-1 rounded bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 transition-colors"
                    >
                      Play Adventure
                    </Link>
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
