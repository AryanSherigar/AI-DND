import { useMutation } from "@tanstack/react-query";
import { uploadMapImage } from "../api/uploads.api";

export const useUploadMapImage = () => {
  return useMutation({
    mutationFn: uploadMapImage,
  });
};
