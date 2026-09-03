import { useMutation } from "@tanstack/react-query";
import { joinPlaythrough } from "../api/share.api";
import { PlaythroughResponse } from "../api/playthroughs.api";

export function useJoinPlaythrough() {
  return useMutation<PlaythroughResponse, Error, string>({
    mutationFn: (shareToken: string) => joinPlaythrough(shareToken),
  });
}
