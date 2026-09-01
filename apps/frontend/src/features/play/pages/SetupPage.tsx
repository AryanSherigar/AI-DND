import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { mockScenarios } from "../mock/scenarios";
import { BackgroundMist } from "../components/PlayScreen/BackgroundMist";
import { SetupStageCard } from "../components/SetupStageCard";
import { DramaticSetupLoader } from "../components/DramaticSetupLoader";

export const SetupPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [is_loading, setIsLoading] = useState(false);

  // Find target scenario or fallback to first mock scenario
  const scenario = mockScenarios.find((s) => s.id === id) || mockScenarios[0];

  const handleSubmit = (
    _formattedPayload: string,
    _formValues: Record<string, unknown>,
  ) => {
    // Trigger dramatic loading overlay transition
    setIsLoading(true);
  };

  const handleLoaderComplete = () => {
    // Navigate to playthrough screen
    navigate(`/play/${scenario.id}`);
  };

  return (
    <div className="relative min-h-screen w-full bg-zinc-950 text-zinc-100 flex items-center justify-center p-4 sm:p-6 md:p-10 overflow-x-hidden font-sans selection:bg-amber-500/30 selection:text-amber-200">
      {/* Background Mist Motion Layer */}
      <BackgroundMist opacity={0.6} blobCount={8} />

      {/* Subtle Background Radial Vignette */}
      <div className="absolute inset-0 bg-radial from-transparent via-zinc-950/70 to-zinc-950 pointer-events-none" />

      {/* Centered Stage Ritual Card */}
      <SetupStageCard scenario={scenario} onSubmit={handleSubmit} />

      {/* Dramatic Loader Transition Modal */}
      {is_loading && (
        <DramaticSetupLoader
          scenarioTitle={scenario.title}
          onComplete={handleLoaderComplete}
        />
      )}
    </div>
  );
};
