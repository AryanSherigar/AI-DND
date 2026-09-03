import { useMutation } from "@tanstack/react-query";
import {
  createPlaythrough,
  CreatePlaythroughPayload,
  PlaythroughResponse,
} from "../api/playthroughs.api";

export function useCreatePlaythrough() {
  return useMutation<PlaythroughResponse, Error, CreatePlaythroughPayload>({
    mutationFn: (payload: CreatePlaythroughPayload) =>
      createPlaythrough(payload),
  });
}
