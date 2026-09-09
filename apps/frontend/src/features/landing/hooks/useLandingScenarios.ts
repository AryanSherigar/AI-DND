import { useQuery } from "@tanstack/react-query";
import { fetchScenarios } from "@/features/play/api/discovery.api";
import {
  ScenarioMock,
  ScenarioSummaryResponse,
} from "@/features/play/types/scenario";

const FALLBACK_COVER_IMAGE_URL = "/images/hero.png";
const LANDING_SCENARIO_LIMIT = 18;

const toScenarioMock = (scenario: ScenarioSummaryResponse): ScenarioMock => ({
  id: scenario.scenario_id,
  title: scenario.title,
  logline: scenario.logline || "No description provided.",
  rating: parseFloat(scenario.rating_avg || "0"),
  playerCount: scenario.play_count,
  genre: scenario.genre_tags[0] || "High Fantasy",
  author: `Creator #${scenario.creator_id.substring(0, 8)}`,
  coverImageUrl: scenario.cover_image_url || FALLBACK_COVER_IMAGE_URL,
});

export const useLandingScenarios = () => {
  const trendingQuery = useQuery({
    queryKey: ["landing-scenarios", "trending"],
    queryFn: () =>
      fetchScenarios({ sort: "rating_avg", limit: LANDING_SCENARIO_LIMIT }),
  });
  const popularQuery = useQuery({
    queryKey: ["landing-scenarios", "popular"],
    queryFn: () =>
      fetchScenarios({ sort: "play_count", limit: LANDING_SCENARIO_LIMIT }),
  });
  const newestQuery = useQuery({
    queryKey: ["landing-scenarios", "newest"],
    queryFn: () =>
      fetchScenarios({ sort: "created_at", limit: LANDING_SCENARIO_LIMIT }),
  });

  return {
    trendingScenarios: (trendingQuery.data?.items ?? []).map(toScenarioMock),
    epicAdventures: (popularQuery.data?.items ?? []).map(toScenarioMock),
    newArrivals: (newestQuery.data?.items ?? []).map(toScenarioMock),
    isLoading:
      trendingQuery.isLoading ||
      popularQuery.isLoading ||
      newestQuery.isLoading,
  };
};
