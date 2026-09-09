import { useState } from "react";
import { signInWithPopup, signInWithEmailAndPassword } from "firebase/auth";
import { auth, googleProvider } from "@/shared/lib/firebase";
import { exchangeFirebaseToken, logoutUser } from "../api/auth.api";
import { useAuthStore } from "../stores/auth.store";
import { extractErrorMessage } from "@/shared/lib/extractErrorMessage";
import {
  DEFAULT_JUDGE_EMAIL,
  DEFAULT_JUDGE_PASSWORD,
} from "../constants/auth.constants";

const formatJudgeAuthError = (err: unknown, email: string): string => {
  const rawMsg = extractErrorMessage(err, "Judge login failed");
  if (
    rawMsg.includes("user-not-found") ||
    rawMsg.includes("invalid-credential") ||
    rawMsg.includes("wrong-password")
  ) {
    return `Judge account (${email}) not found in Firebase. Please enable Email/Password auth and add this user in the Firebase Console.`;
  }
  return rawMsg;
};

export const useAuth = () => {
  const {
    user,
    isAuthenticated,
    isLoading,
    setAuth,
    logout: storeLogout,
  } = useAuthStore();
  const [error, setError] = useState<string | null>(null);
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [isJudgeLoading, setIsJudgeLoading] = useState(false);

  const loginWithGoogle = async () => {
    setIsGoogleLoading(true);
    try {
      const result = await signInWithPopup(auth, googleProvider);
      const idToken = await result.user.getIdToken();

      const { access_token, user: apiUser } =
        await exchangeFirebaseToken(idToken);
      setAuth(access_token, apiUser);
      setError(null);
    } catch (err: unknown) {
      setError(extractErrorMessage(err, "Login failed"));
    } finally {
      setIsGoogleLoading(false);
    }
  };

  const loginAsJudge = async () => {
    setIsJudgeLoading(true);
    const email = import.meta.env.VITE_JUDGE_EMAIL || DEFAULT_JUDGE_EMAIL;
    const password =
      import.meta.env.VITE_JUDGE_PASSWORD || DEFAULT_JUDGE_PASSWORD;

    try {
      const result = await signInWithEmailAndPassword(auth, email, password);
      const idToken = await result.user.getIdToken();
      const { access_token, user: apiUser } =
        await exchangeFirebaseToken(idToken);
      setAuth(access_token, apiUser);
      setError(null);
    } catch (err: unknown) {
      setError(formatJudgeAuthError(err, email));
    } finally {
      setIsJudgeLoading(false);
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
    isGoogleLoading,
    isJudgeLoading,
    error,
    loginWithGoogle,
    loginAsJudge,
    loginAsDevUser,
    logout,
  };
};
