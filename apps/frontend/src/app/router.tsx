import React from 'react';
import { createBrowserRouter } from 'react-router-dom';
import { LoginPage } from '@/features/auth/pages/LoginPage';
import { AuthGuard } from '@/features/auth/components/AuthGuard/AuthGuard';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { LandingPage } from '@/features/play/pages/LandingPage';

const StudioPlaceholder: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center p-6 text-white">
      <div className="max-w-lg w-full bg-zinc-900 border border-zinc-800 rounded-xl p-8 shadow-xl">
        <h1 className="text-3xl font-bold mb-4 text-emerald-400">Studio (Authenticated)</h1>
        <p className="text-zinc-300 mb-6">Welcome to the AI-DND Creator Studio.</p>

        <div className="space-y-3 bg-zinc-950 p-4 rounded-lg border border-zinc-800 font-mono text-sm mb-6">
          <div>
            <span className="text-zinc-500">User ID:</span> {user?.user_id}
          </div>
          <div>
            <span className="text-zinc-500">Display Name:</span> {user?.display_name}
          </div>
        </div>

        <button
          onClick={logout}
          className="w-full px-4 py-2 bg-red-600 hover:bg-red-700 font-semibold rounded-lg transition-colors"
        >
          Sign Out
        </button>
      </div>
    </div>
  );
};

export const router = createBrowserRouter([
  {
    path: '/',
    element: <LandingPage />,
  },
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/studio',
    element: (
      <AuthGuard>
        <StudioPlaceholder />
      </AuthGuard>
    ),
  },
]);
