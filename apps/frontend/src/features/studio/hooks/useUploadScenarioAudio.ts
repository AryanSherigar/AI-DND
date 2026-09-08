import { useMutation } from "@tanstack/react-query";
import { uploadScenarioAudio } from "../api/uploads.api";

/** Shared authenticated upload mutation for bounded Dodge audio assets. */
export const useUploadScenarioAudio = () =>
  useMutation({ mutationFn: uploadScenarioAudio });