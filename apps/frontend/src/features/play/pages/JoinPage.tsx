import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { useJoinPlaythrough } from "../hooks/useJoinPlaythrough";

export function JoinPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const joinMutation = useJoinPlaythrough();
  const hasAttemptedRef = useRef(false);

  useEffect(() => {
    if (isAuthLoading) return;
    if (!isAuthenticated) {
      navigate(`/login?redirect=/join?token=${token ?? ""}`, { replace: true });
      return;
    }
    if (!token || hasAttemptedRef.current) return;

    hasAttemptedRef.current = true;
    joinMutation.mutate(token, {
      onSuccess: (data) => {
        navigate(`/play/${data.playthrough_id}`, { replace: true });
      },
    });
  }, [isAuthLoading, isAuthenticated, token, navigate, joinMutation]);

  if (!token) {
    return (
      <div className="min-h-screen w-full bg-stone-950 text-stone-100 flex items-center justify-center p-6 text-center">
        <p className="font-mono text-sm text-red-400">
          Missing or invalid join link.
        </p>
      </div>
    );
  }

  if (joinMutation.isError) {
    return (
      <div className="min-h-screen w-full bg-stone-950 text-stone-100 flex items-center justify-center p-6 text-center">
        <p className="font-mono text-sm text-red-400">
          This join link is invalid, expired, or this scenario doesn't support
          multiplayer.
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-full bg-stone-950 flex flex-col items-center justify-center space-y-4">
      <div className="w-10 h-10 border-2 border-amber-500/30 border-t-amber-500 rounded-full animate-spin" />
      <p className="font-mono text-xs text-amber-500/80 tracking-widest uppercase">
        Joining session...
      </p>
    </div>
  );
}

export default JoinPage;
