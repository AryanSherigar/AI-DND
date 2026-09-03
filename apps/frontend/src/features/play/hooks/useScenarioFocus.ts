import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchScenarioDetail,
  toggleBookmarkApi,
  fetchScenarioReviews,
  submitScenarioReview,
  fetchPublicPlaythroughs,
} from "../api/scenarioFocus.api";
import { mockScenarios } from "../mock/scenarios";
import {
  ScenarioDetailResponse,
  ScenarioMock,
  ScenarioReviewListResponse,
} from "../types/scenario";
import { useAuth } from "@/features/auth/hooks/useAuth";

const LOCAL_BOOKMARKS_KEY = "aidnd_bookmarks";

const getLocalBookmarks = (): string[] => {
  try {
    const raw = localStorage.getItem(LOCAL_BOOKMARKS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
};

const setLocalBookmarks = (bookmarks: string[]) => {
  try {
    localStorage.setItem(LOCAL_BOOKMARKS_KEY, JSON.stringify(bookmarks));
  } catch {
    // Ignore storage write errors
  }
};

export const useScenarioFocus = (scenarioId: string | undefined) => {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [isLocalBookmarked, setIsLocalBookmarked] = useState<boolean>(false);

  useEffect(() => {
    if (!scenarioId) return;
    const localList = getLocalBookmarks();
    setIsLocalBookmarked(localList.includes(scenarioId));
  }, [scenarioId]);

  // Query scenario detail from API with fallback to mockScenarios
  const scenarioQuery = useQuery({
    queryKey: ["scenario-detail", scenarioId],
    queryFn: async (): Promise<ScenarioDetailResponse> => {
      if (!scenarioId) throw new Error("Scenario ID is required");
      try {
        return await fetchScenarioDetail(scenarioId);
      } catch {
        // Fallback for mock IDs
        const mockItem = mockScenarios.find(
          (item: ScenarioMock) => item.id === scenarioId,
        );
        if (mockItem) {
          return {
            scenario_id: mockItem.id,
            creator_id: "mock-creator-id",
            creator_display_name: mockItem.author,
            title: mockItem.title,
            logline: mockItem.logline,
            mode: "newbie",
            status: "published",
            genre_tags: [mockItem.genre],
            complexity_tier: "newbie",
            player_count_support: "solo",
            estimated_playtime: "30-45 mins",
            cover_image_url: mockItem.coverImageUrl,
            content_tag: "PG-13",
            play_count: mockItem.playerCount,
            rating_avg: mockItem.rating.toString(),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            is_bookmarked: false,
            can_review: false,
            world_data: {
              lore: "Deep in the forgotten realms, dark mysteries await brave adventurers. Uncover hidden secrets and brave dangerous hazards in this immersive text experience.",
            },
            setup_schema: mockItem.setupInputs || [],
          };
        }
        throw new Error("Scenario not found");
      }
    },
    enabled: Boolean(scenarioId),
  });

  // NOTE: queryFn deliberately does not catch-and-fall-back-to-empty here.
  // Swallowing errors turned a transient failure (including a request
  // aborted by React Query's own refetch deduplication, which surfaces as a
  // rejected fetch) into a fake "empty" success response — which then
  // overwrote genuinely-loaded review data with nothing. Letting the error
  // propagate lets React Query keep showing the last good `data` while
  // `isError`/`isFetching` reflect the real state, instead of clobbering it.
  const reviewsQuery = useQuery({
    queryKey: ["scenario-reviews", scenarioId],
    queryFn: () => {
      if (!scenarioId) throw new Error("Scenario ID is required");
      return fetchScenarioReviews(scenarioId);
    },
    enabled: Boolean(scenarioId),
  });

  const playthroughsQuery = useQuery({
    queryKey: ["scenario-public-playthroughs", scenarioId],
    queryFn: () => {
      if (!scenarioId) throw new Error("Scenario ID is required");
      return fetchPublicPlaythroughs(scenarioId);
    },
    enabled: Boolean(scenarioId),
  });

  // Bookmark Mutation
  const bookmarkMutation = useMutation({
    mutationFn: async () => {
      if (!scenarioId) return;
      if (user) {
        return await toggleBookmarkApi(scenarioId);
      }
      // Guest local storage toggle
      const currentList = getLocalBookmarks();
      const nextList = currentList.includes(scenarioId)
        ? currentList.filter((id) => id !== scenarioId)
        : [...currentList, scenarioId];
      setLocalBookmarks(nextList);
      setIsLocalBookmarked(nextList.includes(scenarioId));
      return { is_bookmarked: nextList.includes(scenarioId) };
    },
    onSuccess: (data) => {
      if (data && user) {
        queryClient.setQueryData(
          ["scenario-detail", scenarioId],
          (old: ScenarioDetailResponse | undefined) =>
            old ? { ...old, is_bookmarked: data.is_bookmarked } : old,
        );
      }
    },
  });

  // Submit Review Mutation
  const reviewMutation = useMutation({
    mutationFn: async ({
      rating,
      comment,
    }: {
      rating: number;
      comment?: string;
    }) => {
      if (!scenarioId) throw new Error("Scenario ID required");
      return await submitScenarioReview(scenarioId, rating, comment);
    },
    onSuccess: (submittedReview) => {
      // Write the mutation's own response directly into the cache instead
      // of relying solely on invalidateQueries' follow-up refetch: a POST
      // immediately followed by a GET on a fresh connection sometimes raced
      // with Postgres/connection-pool visibility, so the refetch could land
      // before the write was visible to it, silently keeping stale data
      // on screen with no error. The mutation response is the ground truth
      // for what was just written, so merge it in directly and unconditionally.
      queryClient.setQueryData(
        ["scenario-reviews", scenarioId],
        (old: ScenarioReviewListResponse | undefined): ScenarioReviewListResponse => {
          const items = old?.items ?? [];
          const existingIndex = items.findIndex(
            (r) => r.user_id === submittedReview.user_id,
          );
          const nextItems =
            existingIndex >= 0
              ? items.map((r, i) => (i === existingIndex ? submittedReview : r))
              : [submittedReview, ...items];
          const totalRating = nextItems.reduce((sum, r) => sum + r.rating, 0);
          return {
            items: nextItems,
            total_count: nextItems.length,
            average_rating: totalRating / nextItems.length,
          };
        },
      );
      // Still invalidate in the background (not awaited) so other viewers'
      // reviews and any server-side rounding eventually reconcile.
      void queryClient.invalidateQueries({
        queryKey: ["scenario-reviews", scenarioId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["scenario-detail", scenarioId],
      });
    },
  });

  const isBookmarked = user
    ? Boolean(scenarioQuery.data?.is_bookmarked)
    : isLocalBookmarked;

  return {
    scenario: scenarioQuery.data,
    isLoading: scenarioQuery.isLoading,
    isError: scenarioQuery.isError,
    reviews: reviewsQuery.data?.items || [],
    totalReviews: reviewsQuery.data?.total_count || 0,
    averageRating: reviewsQuery.data?.average_rating || 0,
    publicPlaythroughs: playthroughsQuery.data || [],
    isBookmarked,
    toggleBookmark: () => bookmarkMutation.mutate(),
    isTogglingBookmark: bookmarkMutation.isPending,
    submitReview: reviewMutation.mutateAsync,
    isSubmittingReview: reviewMutation.isPending,
    currentUser: user,
  };
};
