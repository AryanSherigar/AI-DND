import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { PlayScreen } from "../components/PlayScreen/PlayScreen";
import { usePlayStore } from "../stores/play.store";

export function PlayPage() {
  const [searchParams] = useSearchParams();
  const playthrough = usePlayStore((s) => s.playthrough);
  const setPlaythrough = usePlayStore((s) => s.setPlaythrough);

  useEffect(() => {
    const isSpectatorMode = searchParams.get("mode") === "spectate";
    if (playthrough && playthrough.is_spectator !== isSpectatorMode) {
      setPlaythrough({
        ...playthrough,
        is_spectator: isSpectatorMode,
      });
    }
  }, [searchParams, playthrough, setPlaythrough]);

  return <PlayScreen />;
}

export default PlayPage;
