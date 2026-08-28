import React, { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../stores/auth.store';
import { useAuth } from '../hooks/useAuth';
import { RetroConsole } from '../components/RetroConsole';

export const LoginPage: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuthStore();
  const { error, loginWithGoogle, loginAsDevUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from?.pathname || '/';

  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, from]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-black">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#8bac0f]"></div>
      </div>
    );
  }

  return (
    <>
      <RetroConsole 
        onStart={loginWithGoogle}
        isError={!!error}
        errorMessage={error}
      />
      {import.meta.env.DEV && (
        <button
          onClick={loginAsDevUser}
          className="fixed bottom-4 right-4 px-3 py-2 bg-zinc-900 border border-zinc-700 text-xs text-zinc-400 rounded opacity-50 hover:opacity-100 transition-opacity z-50"
        >
          Dev Login Bypass
        </button>
      )}
    </>
  );
};
