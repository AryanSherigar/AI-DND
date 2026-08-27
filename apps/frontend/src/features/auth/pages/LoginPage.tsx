import React, { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../stores/auth.store';
import { useAuth } from '../hooks/useAuth';
import { LoginButton } from '../components/LoginButton/LoginButton';

export const LoginPage: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuthStore();
  const { error, loginAsDevUser } = useAuth();
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
      <div className="min-h-screen flex items-center justify-center bg-zinc-950">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-500"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8 bg-zinc-900 p-10 rounded-xl shadow-2xl border border-zinc-800">
        <div>
          <h2 className="mt-2 text-center text-4xl font-extrabold text-white tracking-tight">
            AI-DND
          </h2>
          <p className="mt-4 text-center text-sm text-zinc-400">
            Sign in to start your adventure or build new worlds.
          </p>
        </div>
        
        {error && (
          <div className="rounded-md bg-red-900/50 border border-red-800 p-4">
            <div className="text-sm text-red-200">{error}</div>
          </div>
        )}

        <div className="mt-8 space-y-4">
          <LoginButton />
          <div className="relative flex py-2 items-center">
            <div className="flex-grow border-t border-zinc-800"></div>
            <span className="flex-shrink mx-4 text-xs text-zinc-500 uppercase font-semibold">Or</span>
            <div className="flex-grow border-t border-zinc-800"></div>
          </div>
          <button
            onClick={loginAsDevUser}
            className="w-full px-4 py-3 border border-zinc-700 text-sm font-medium rounded-lg text-zinc-200 bg-zinc-800 hover:bg-zinc-700 transition-colors"
          >
            ⚡ Dev Quick Login (No Firebase Required)
          </button>
        </div>
      </div>
    </div>
  );
};
