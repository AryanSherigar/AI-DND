import { useMemo } from "react";
import { mockScenarios } from "../mock/scenarios";

export const useDiscovery = (searchParams: URLSearchParams) => {
  const filteredScenarios = useMemo(() => {
    let result = [...mockScenarios];

    // 1. Text Search
    const query = searchParams.get("q")?.toLowerCase();
    if (query) {
      result = result.filter(
        (s) =>
          s.title.toLowerCase().includes(query) ||
          s.logline.toLowerCase().includes(query) ||
          s.author.toLowerCase().includes(query),
      );
    }

    // 2. Mode (Complexity)
    const mode = searchParams.get("mode");
    if (mode && mode !== "all") {
      // Mock logic: randomly filter based on mode to simulate real filtering
      // since our mock data doesn't have mode explicitely, we assume based on ID
      // just to have some visuals.
      result = result.filter((s) => {
        if (mode === "master") return parseInt(s.id) % 2 === 0;
        if (mode === "newbie") return parseInt(s.id) % 2 !== 0;
        return true;
      });
    }

    // 3. Player Count
    const playerCount = searchParams.get("playerCount");
    if (playerCount && playerCount !== "all") {
      result = result.filter((s) => {
        if (playerCount === "solo") return s.id !== "3"; // just mock filtering
        return true;
      });
    }

    // 4. Genres (Support multiple)
    const genres = searchParams.getAll("genre");
    if (genres.length > 0) {
      result = result.filter((s) => genres.includes(s.genre.toLowerCase()));
    }

    // 5. Min Plays
    const minPlays = searchParams.get("minPlays");
    if (minPlays) {
      result = result.filter((s) => s.playerCount >= parseInt(minPlays));
    }

    // 6. Sort
    const sort = searchParams.get("sort");
    if (sort === "popular") {
      result.sort((a, b) => b.playerCount - a.playerCount);
    } else if (sort === "trending") {
      result.sort((a, b) => b.rating - a.rating); // mockup trending via rating
    }

    return result;
  }, [searchParams]);

  return {
    data: filteredScenarios,
    isLoading: false, // In a real react-query setup, this would be dynamic
    isError: false,
  };
};
