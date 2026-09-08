import { useMutation } from "@tanstack/react-query";
import { generateCoverImage } from "../api/uploads.api";

export const useGenerateCoverImage = () => {
  return useMutation({
    mutationFn: generateCoverImage,
  });
};
