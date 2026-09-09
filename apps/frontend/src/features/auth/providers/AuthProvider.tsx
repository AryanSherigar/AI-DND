import React, { useEffect } from "react";
import { useAuthStore } from "../stores/auth.store";
import { refreshAccessToken } from "../api/auth.api";

interface AuthProviderProps {
  children: React.ReactNode;
}

const AUTH_INIT_TIMEOUT_MS = 3000;

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const { setAuth, logout, setLoading } = useAuthStore();

  useEffect(() => {
    let isMounted = true;

    const safetyTimer = setTimeout(() => {
      if (isMounted) {
        setLoading(false);
      }
    }, AUTH_INIT_TIMEOUT_MS);

    const initAuth = async () => {
      try {
        const { access_token, user } = await refreshAccessToken();
        if (isMounted) {
          setAuth(access_token, user);
        }
      } catch {
        if (isMounted) {
          logout();
        }
      } finally {
        clearTimeout(safetyTimer);
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    initAuth();

    return () => {
      isMounted = false;
      clearTimeout(safetyTimer);
    };
  }, [setAuth, logout, setLoading]);

  return <>{children}</>;
};
