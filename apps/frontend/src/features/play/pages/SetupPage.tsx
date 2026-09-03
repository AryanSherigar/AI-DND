import React, { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { useScenarioFocus } from "../hooks/useScenarioFocus";
import { useCreatePlaythrough } from "../hooks/useSetup";
import { BackgroundMist } from "../components/PlayScreen/BackgroundMist";
import { SetupStageCard } from "../components/SetupScreen/SetupStageCard";
import { DramaticSetupLoader } from "../components/SetupScreen/DramaticSetupLoader";
import { Toast } from "@/shared/components/feedback/Toast";

export const SetupPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const {
    scenario,
    isLoading: isScenarioLoading,
    isError: isScenarioError,
  } = useScenarioFocus(id);
  const createPlaythroughMutation = useCreatePlaythrough();

  const [isLoadingOverlay, setIsLoadingOverlay] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const playthroughIdRef = useRef<string | null>(null);
  const loaderFinishedRef = useRef<boolean>(false);

  // Auth Redirect Guard
  useEffect(() => {
    if (!isAuthLoading && !isAuthenticated && id) {
      navigate(`/login?redirect=/setup/${id}`, { replace: true });
    }
  }, [isAuthenticated, isAuthLoading, id, navigate]);

  const handleSubmit = async (
    _formattedPayload: string,
    formValues: Record<string, unknown>,
  ) => {
    if (!scenario) return;

    setErrorMessage(null);
    playthroughIdRef.current = null;
    loaderFinishedRef.current = false;
    setIsLoadingOverlay(true);

    try {
      const targetScenarioId =
        scenario.scenario_id || (scenario as any).id || id || "";
      const result = await createPlaythroughMutation.mutateAsync({
        scenario_id: targetScenarioId,
        setup_values: formValues,
      });

      playthroughIdRef.current = result.playthrough_id;

      // If animation already completed while waiting for API
      if (loaderFinishedRef.current) {
        navigate(`/play/${result.playthrough_id}`);
      }
    } catch (err: any) {
      setIsLoadingOverlay(false);
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        "Failed to initialize campaign. Please check your setup choices and try again.";
      setErrorMessage(
        typeof detail === "string" ? detail : JSON.stringify(detail),
      );
    }
  };

  const handleLoaderComplete = () => {
    loaderFinishedRef.current = true;
    if (playthroughIdRef.current) {
      navigate(`/play/${playthroughIdRef.current}`);
    }
  };

  if (isAuthLoading || isScenarioLoading) {
    return (
      <div className="min-h-screen w-full bg-zinc-950 flex flex-col items-center justify-center space-y-4">
        <div className="w-10 h-10 border-2 border-amber-500/30 border-t-amber-500 rounded-full animate-spin" />
        <p className="font-mono text-xs text-amber-500/80 tracking-widest uppercase">
          CALIBRATING SCENARIO REALM...
        </p>
      </div>
    );
  }

  if (isScenarioError || !scenario) {
    return (
      <div className="min-h-screen w-full bg-zinc-950 text-zinc-100 flex flex-col items-center justify-center p-6 text-center space-y-6">
        <BackgroundMist opacity={0.4} blobCount={4} />
        <div className="z-10 space-y-3">
          <h1 className="font-serif text-3xl font-bold text-red-400">
            Scenario Not Found
          </h1>
          <p className="font-mono text-xs text-zinc-400 max-w-md">
            The requested scenario could not be loaded or is unavailable.
          </p>
          <button
            onClick={() => navigate("/discover")}
            className="px-6 py-3 bg-zinc-900 border border-zinc-800 rounded-lg text-xs font-mono uppercase tracking-wider text-amber-400 hover:bg-zinc-800 transition-colors"
          >
            Return to Discover
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen w-full bg-zinc-950 text-zinc-100 flex items-center justify-center p-4 sm:p-6 md:p-10 overflow-x-hidden font-sans selection:bg-amber-500/30 selection:text-amber-200">
      <BackgroundMist opacity={0.6} blobCount={8} />

      <div className="absolute inset-0 bg-radial from-transparent via-zinc-950/70 to-zinc-950 pointer-events-none" />

      <SetupStageCard
        scenario={scenario}
        onSubmit={handleSubmit}
        isSubmitting={createPlaythroughMutation.isPending || isLoadingOverlay}
      />

      {isLoadingOverlay && (
        <DramaticSetupLoader
          scenarioTitle={scenario.title}
          onComplete={handleLoaderComplete}
        />
      )}

      {errorMessage && (
        <Toast
          message={errorMessage}
          type="error"
          onClose={() => setErrorMessage(null)}
        />
      )}
    </div>
  );
};
