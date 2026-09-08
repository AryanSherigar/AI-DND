import { useQuery } from "@tanstack/react-query";
import { getMusicGenerationJob } from "../api/music.api";
import { MusicGenerationJob } from "../types/music.types";

const POLL_INTERVAL_MS = 2000;

const isTerminalStatus = (job: MusicGenerationJob | undefined): boolean =>
  job?.status === "succeeded" || job?.status === "failed";

/** Polls a submitted Lyria job's status until it reaches a terminal state.
 * Core-api is stateless/no-streaming, so this poll replaces SSE for the
 * Studio's authoring-time generation flow. */
export const useMusicGenerationJob = (
  scenarioId: string | null,
  jobId: string | null,
) => {
  return useQuery({
    queryKey: ["music-generation-job", scenarioId, jobId],
    queryFn: () => getMusicGenerationJob(scenarioId as string, jobId as string),
    enabled: Boolean(scenarioId) && Boolean(jobId),
    refetchInterval: (query) =>
      isTerminalStatus(query.state.data) ? false : POLL_INTERVAL_MS,
  });
};
