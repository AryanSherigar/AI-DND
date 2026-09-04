import { useMutation } from "@tanstack/react-query";
import { uploadCoverImage } from "../api/uploads.api";

export const useUploadCoverImage = () => {
  return useMutation({
    mutationFn: uploadCoverImage,
  });
};
