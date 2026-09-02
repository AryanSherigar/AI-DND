import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchScenarios } from "../api/discovery.api";
import { mockScenarios } from "../mock/scenarios";
import {
  GetScenariosParams,
  ScenarioMock,
  ScenarioSummaryResponse,
} from "../types/scenario";

export type DisplayScenario = ScenarioSummaryResponse | ScenarioMock;

export const useDiscovery = (searchParams: URLSearchParams) => {
  const params: GetScenariosParams = useMemo(() => {
    const mineParam = searchParams.get("mine");
    const modeParam = searchParams.get("mode");
    const playerParam = searchParams.get("playerCount");
    const sortParam = searchParams.get("sort");
    const genres = searchParams.getAll("genre");

    const queryParams: GetScenariosParams = {};

    if (mineParam === "true") {
      queryParams.mine = true;
    }

    if (modeParam === "newbie" || modeParam === "master") {
      queryParams.complexity_tier = modeParam;
    }

    if (
      playerParam === "solo" ||
      playerParam === "multiplayer" ||
      playerParam === "both"
    ) {
      queryParams.player_count_support = playerParam;
    }

    if (sortParam === "popular") {
      queryParams.sort = "play_count";
    } else if (sortParam === "trending") {
      queryParams.sort = "rating_avg";
    } else {
      queryParams.sort = "created_at";
    }

    if (genres.length > 0) {
      queryParams.genre_tags = genres;
    }

    return queryParams;
  }, [searchParams]);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["scenarios", params],
    queryFn: () => fetchScenarios(params),
  });

  const displayScenarios = useMemo(() => {
    const queryText = searchParams.get("q")?.toLowerCase();

    // 1. If backend API returned items from DB, display them
    if (data?.items && data.items.length > 0) {
      let items = data.items;
      if (queryText) {
        items = items.filter(
          (s) =>
            s.title.toLowerCase().includes(queryText) ||
            (s.logline && s.logline.toLowerCase().includes(queryText)),
        );
      }
      return items;
    }

    // 2. Dev fallback to mock data only if DB returns 0 items
    if (import.meta.env.DEV && (!data || data.total_count === 0)) {
      let mockList = [...mockScenarios];

      if (queryText) {
        mockList = mockList.filter(
          (s) =>
            s.title.toLowerCase().includes(queryText) ||
            s.logline.toLowerCase().includes(queryText) ||
            s.author.toLowerCase().includes(queryText),
        );
      }

      return mockList;
    }

    return [];
  }, [data, searchParams]);

  return {
    data: displayScenarios,
    totalCount: data?.total_count ?? displayScenarios.length,
    isLoading,
    isError,
    error,
  };
};
