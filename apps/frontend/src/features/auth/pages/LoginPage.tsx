import React, { useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { motion } from "motion/react";
import { useAuthStore } from "../stores/auth.store";
import { useAuth } from "../hooks/useAuth";
import { LoginHero } from "../components/LoginHero/LoginHero";
import { GoogleSignInButton } from "../components/GoogleSignInButton/GoogleSignInButton";
import { LayoutTextFlip } from "@/shared/components/ui/aceternity/layout-text-flip";
import { Loader } from "@/shared/components/feedback/Loader";

const LOGIN_BG = "#f7f5f1";
const FLIP_WORDS = ["a new world", "a living story", "your legend", "the unknown"];
const FLIP_LIGHT =
  "bg-white text-neutral-900 ring-black/10 shadow-black/10 dark:bg-white dark:text-neutral-900 dark:ring-black/10 dark:shadow-black/10";

export const LoginPage: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuthStore();
  const { error, loginWithGoogle, loginAsDevUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from?.pathname || "/";

  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, from]);

  if (isLoading) {
    return (
      <div
        className="flex min-h-screen items-center justify-center"
        style={{ backgroundColor: LOGIN_BG }}
      >
        <Loader size="lg" label="Loading" />
      </div>
    );
  }

  return (
    <main
      className="relative min-h-screen overflow-hidden text-neutral-900"
      style={{ backgroundColor: LOGIN_BG }}
    >
      {/* Image plate — bleeds well past the 65% line and under the panel,
          so the panel's fade has plenty of photo to dissolve. */}
      <div className="absolute inset-y-0 left-0 hidden w-[80%] lg:block">
        <LoginHero />
      </div>

      {/* Content panel — its own background is a left-to-right fade so the
          image dissolves into paper across ~260px of overlap. */}
      <div
        className="relative ml-auto flex min-h-screen w-full items-center px-8 py-16 sm:px-14 lg:w-[46%] lg:pl-44"
        style={{
          background: `linear-gradient(to right, ${LOGIN_BG}00 0%, ${LOGIN_BG}b3 120px, ${LOGIN_BG} 260px)`,
        }}
      >
        <div className="w-full max-w-md">
          <span className="block font-mono text-5xl font-semibold lowercase tracking-[0.12em] text-neutral-900 sm:text-6xl">
            wevr
          </span>

          <motion.div className="mt-8 flex flex-row flex-nowrap items-center gap-x-2 whitespace-nowrap text-neutral-900">
            <LayoutTextFlip
              text="Step into"
              words={FLIP_WORDS}
              size="sm"
              className={FLIP_LIGHT}
              textClassName="text-neutral-900"
            />
          </motion.div>

          <div className="mt-10">
            <GoogleSignInButton onClick={loginWithGoogle} />
          </div>

          {error && (
            <p
              role="alert"
              className="mt-4 rounded-md border border-red-300 bg-red-50 px-3 py-2 font-sans text-xs text-red-700"
            >
              {error}
            </p>
          )}

          <p className="mt-8 font-sans text-xs leading-relaxed text-neutral-500">
            By continuing you agree to the terms of use. wevr only reads your
            name and email from Google.
          </p>

          {import.meta.env.DEV && (
            <button
              onClick={loginAsDevUser}
              className="mt-6 font-mono text-xs text-neutral-400 underline decoration-dotted underline-offset-4 transition hover:text-neutral-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-400"
            >
              Dev login bypass
            </button>
          )}
        </div>
      </div>
    </main>
  );
};
