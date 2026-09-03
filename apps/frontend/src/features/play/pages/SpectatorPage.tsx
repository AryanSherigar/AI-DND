import { useParams, useSearchParams } from "react-router-dom";
import { SpectatorView } from "../components/SpectatorView/SpectatorView";
import { usePlaythroughTurns } from "../hooks/useTurns";
import { useSpectator } from "../hooks/useSpectator";

export function SpectatorPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const shareToken = searchParams.get("token");

  const { data, isLoading, isError } = usePlaythroughTurns(
    id,
    shareToken ? { share_token: shareToken } : {},
  );
  const { streamingText, isLive } = useSpectator(id ?? null, shareToken);

  if (!id || !shareToken) {
    return (
      <div className="min-h-screen w-full bg-stone-950 text-stone-100 flex items-center justify-center p-6 text-center">
        <p className="font-mono text-sm text-red-400">
          Missing or invalid spectator link.
        </p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="min-h-screen w-full bg-stone-950 flex items-center justify-center">
        <div className="w-10 h-10 border-2 border-amber-500/30 border-t-amber-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="min-h-screen w-full bg-stone-950 text-stone-100 flex items-center justify-center p-6 text-center">
        <p className="font-mono text-sm text-red-400">
          This spectator link is invalid or has expired.
        </p>
      </div>
    );
  }

  return (
    <SpectatorView
      scenarioTitle="Live Playthrough"
      turns={data.items}
      streamingText={streamingText}
      isLive={isLive}
    />
  );
}

export default SpectatorPage;
