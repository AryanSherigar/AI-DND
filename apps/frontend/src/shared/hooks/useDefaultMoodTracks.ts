import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/lib/api-client";
import { ScenarioMood } from "@/shared/types/audio.types";

const STALE_TIME_MS = 24 * 60 * 60 * 1000;

interface DefaultMusicTracksResponse {
  tracks: Record<ScenarioMood, string>;
}

const getDefaultMusicTracks = async (): Promise<
  Record<ScenarioMood, string>
> => {
  const response =
    await apiClient.get<DefaultMusicTracksResponse>("/v1/music/defaults");
  return response.data.tracks;
};

/** The 6 canonical built-in default mood tracks. These change essentially
 * never, so a long staleTime avoids refetching on every mount. */
export function useDefaultMoodTracks() {
  return useQuery({
    queryKey: ["default-mood-tracks"],
    queryFn: getDefaultMusicTracks,
    staleTime: STALE_TIME_MS,
  });
}
