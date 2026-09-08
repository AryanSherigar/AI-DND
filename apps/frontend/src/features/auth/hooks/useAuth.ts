import { useState } from "react";
import { signInWithPopup } from "firebase/auth";
import { auth, googleProvider } from "@/shared/lib/firebase";
import { exchangeFirebaseToken, logoutUser } from "../api/auth.api";
import { useAuthStore } from "../stores/auth.store";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";

export const useAuth = () => {
  const {
    user,
    isAuthenticated,
    isLoading,
    setAuth,
    logout: storeLogout,
  } = useAuthStore();
  const [error, setError] = useState<string | null>(null);

  const loginWithGoogle = async () => {
    try {
      const result = await signInWithPopup(auth, googleProvider);
      const idToken = await result.user.getIdToken();

      const { access_token, user: apiUser } =
        await exchangeFirebaseToken(idToken);
      setAuth(access_token, apiUser);
      setError(null);
    } catch (err: unknown) {
      setError(extractErrorMessage(err, "Login failed"));
    }
  };

  const loginAsDevUser = async () => {
    if (!import.meta.env.DEV) {
      setError("Dev login is unavailable in this environment.");
      return;
    }
    try {
      const { access_token, user: apiUser } =
        await exchangeFirebaseToken("mock-dev-token");
      setAuth(access_token, apiUser);
      setError(null);
    } catch (err: unknown) {
      setError(extractErrorMessage(err, "Dev login failed"));
    }
  };

  const logout = async () => {
    try {
      await logoutUser();
    } catch {
      // NOTE: proceed with client-side logout even if the backend call
      // fails — a network error here shouldn't trap the user in a
      // logged-in UI state.
    }
    if (auth.currentUser) {
      await auth.signOut();
    }
    storeLogout();
  };

  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    loginWithGoogle,
    loginAsDevUser,
    logout,
  };
};
