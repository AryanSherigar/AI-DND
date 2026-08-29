import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/features/auth/hooks/useAuth';

export const Header: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <header className="fixed top-0 left-0 right-0 z-50 px-6 py-4 flex items-center justify-between">
      {/* Skeuomorphic frosted glass container */}
      <div className="absolute inset-0 bg-white/5 backdrop-blur-lg border-b border-white/20 shadow-[inset_0_1px_1px_rgba(255,255,255,0.4),0_4px_20px_rgba(0,0,0,0.5)]"></div>
      
      {/* Content */}
      <div className="relative z-10 flex items-center justify-between w-full max-w-7xl mx-auto">
        {/* Left: Logo */}
        <Link to="/" className="flex items-center gap-2">
          <span className="font-retro text-white text-xl tracking-wider drop-shadow-md">AI-DND</span>
        </Link>

        {/* Center: Nav */}
        <nav className="hidden md:flex items-center gap-8 font-playfair font-medium text-lg text-white/90">
          <Link to="/discover" className="hover:text-white transition-colors drop-shadow-sm hover:drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]">Discover</Link>
          <Link to="/studio" className="hover:text-white transition-colors drop-shadow-sm hover:drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]">Create Scenario</Link>
        </nav>

        {/* Right: Auth */}
        <div className="flex items-center gap-4 font-playfair">
          {user ? (
            <div className="flex items-center gap-4">
              <span className="text-white/80">{user.display_name}</span>
              <button 
                onClick={logout}
                className="px-4 py-2 rounded-md bg-white/10 hover:bg-white/20 border border-white/20 shadow-[inset_0_1px_1px_rgba(255,255,255,0.3)] transition-all text-white"
              >
                Sign Out
              </button>
            </div>
          ) : (
            <Link 
              to="/login"
              className="px-5 py-2 rounded-md bg-white/10 hover:bg-white/20 border border-white/20 shadow-[inset_0_1px_1px_rgba(255,255,255,0.3)] transition-all text-white font-medium"
            >
              Sign In
            </Link>
          )}
        </div>
      </div>
    </header>
  );
};
