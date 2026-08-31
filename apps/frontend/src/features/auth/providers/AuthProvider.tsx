import React, { useEffect } from "react";
import { useAuthStore } from "../stores/auth.store";
import { refreshAccessToken } from "../api/auth.api";

interface AuthProviderProps {
  children: React.ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const { setAuth, logout, setLoading } = useAuthStore();

  useEffect(() => {
    const initAuth = async () => {
      try {
        const { access_token, user } = await refreshAccessToken();
        setAuth(access_token, user);
      } catch (error) {
        logout();
      } finally {
        setLoading(false);
      }
    };

    initAuth();
  }, [setAuth, logout, setLoading]);

  return <>{children}</>;
};
