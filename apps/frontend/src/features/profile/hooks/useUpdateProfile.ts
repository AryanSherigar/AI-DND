import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateProfile } from "../api/profileApi";
import { UserProfile, UserProfileUpdatePayload } from "../types/profile.types";
import { useAuthStore } from "@/features/auth/stores/auth.store";

export const useUpdateProfile = () => {
  const queryClient = useQueryClient();

  return useMutation<UserProfile, Error, UserProfileUpdatePayload>({
    mutationFn: updateProfile,
    onSuccess: (updatedProfile) => {
      queryClient.setQueryData(["user-profile", "me"], updatedProfile);
      queryClient.setQueryData(
        ["user-profile", updatedProfile.user_id],
        updatedProfile,
      );

      // Keep auth store synced with new display name
      const currentAuthUser = useAuthStore.getState().user;
      if (currentAuthUser && updatedProfile.display_name) {
        useAuthStore.setState({
          user: {
            ...currentAuthUser,
            display_name: updatedProfile.display_name,
          },
        });
      }
    },
  });
};
