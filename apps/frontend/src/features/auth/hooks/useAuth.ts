import { useState } from 'react';
import { signInWithPopup } from 'firebase/auth';
import { auth, googleProvider } from '@/shared/lib/firebase';
import { exchangeFirebaseToken } from '../api/auth.api';
import { useAuthStore } from '../stores/auth.store';

export const useAuth = () => {
  const { user, isAuthenticated, isLoading, setAuth, logout: storeLogout } = useAuthStore();
  const [error, setError] = useState<string | null>(null);

  const loginWithGoogle = async () => {
    try {
      const result = await signInWithPopup(auth, googleProvider);
      const idToken = await result.user.getIdToken();
      
      const { access_token, user: apiUser } = await exchangeFirebaseToken(idToken);
      setAuth(access_token, apiUser);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Login failed');
    }
  };

  const logout = async () => {
    await auth.signOut();
    storeLogout();
  };

  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    loginWithGoogle,
    logout,
  };
};
