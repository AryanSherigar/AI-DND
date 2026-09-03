import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/shared/components/ui/Button";
import { usePlaytest } from "../../hooks/usePlaytest";
import { PlaytestButtonProps } from "./PlaytestButton.types";

export const PlaytestButton: React.FC<PlaytestButtonProps> = ({
  scenarioId,
}) => {
  const navigate = useNavigate();
  const { playtest, playthrough, isPlaytesting, playtestError } =
    usePlaytest(scenarioId);

  useEffect(() => {
    if (playthrough) {
      navigate(`/play/${playthrough.playthrough_id}`);
    }
  }, [playthrough, navigate]);

  const handlePlaytest = (): void => {
    playtest();
  };

  return (
    <div className="flex flex-col items-start gap-1">
      <Button
        variant="secondary"
        onClick={handlePlaytest}
        disabled={isPlaytesting}
      >
        {isPlaytesting ? "Starting playtest..." : "Playtest"}
      </Button>
      {playtestError && <p className="text-xs text-red-400">{playtestError}</p>}
    </div>
  );
};
